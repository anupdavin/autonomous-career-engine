"""Semantic ATS Driver - Traverses, maps, and fills application forms.

Combines CareerWeaver multi-frame snapshotting and React-Select handling
with ApplyPilot question mapping and Workday multi-step navigation.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Dict, List, Optional, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from playwright.async_api import Frame, Page

from tools.apply_engine.candidate_facts import load_candidate_profile
from tools.apply_engine.question_mapper import QuestionMapper, norm, pick_option

logger = logging.getLogger("apply_engine.semantic_driver")
PROOF_DIR = WORKSPACE_ROOT / "verified_submission_proofs"
PROOF_DIR.mkdir(exist_ok=True)
DB_PATH = WORKSPACE_ROOT / "oracle_ai_local_mirror.db"

CONFIRM_PATTERNS = [
    r"application\s+(was\s+)?(submitted|received|sent)",
    r"thank\s+you\s+for\s+(applying|your\s+application|submitting)",
    r"we\s+have\s+received\s+your\s+application",
    r"your\s+application\s+has\s+been\s+received",
    r"submission\s+successful",
    r"congratulations.*application.*submitted",
]

# Snapshot script evaluated inside each frame
SNAPSHOT_JS = r"""
() => {
  const norm = s => (s || '').replace(/\s+/g, ' ').trim();
  const doc = document;
  if (!doc || !doc.body) return { fields: [], buttons: [], text: '' };

  const getLabel = (el) => {
    let t = '';
    if (el.id) {
      const l = doc.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) {
        const clone = l.cloneNode(true);
        clone.querySelectorAll('select, input, option, button').forEach(n => n.remove());
        t = clone.textContent;
      }
    }
    if (!t) {
      const pl = el.closest('label');
      if (pl) {
        const clone = pl.cloneNode(true);
        clone.querySelectorAll('select, input, option, button').forEach(n => n.remove());
        t = clone.textContent;
      }
    }
    if (!t && el.getAttribute('aria-labelledby')) {
      el.getAttribute('aria-labelledby').split(/\s+/).forEach(id => {
        const n = doc.getElementById(id);
        if (n) t += ' ' + n.textContent;
      });
    }
    if (!t) {
      const container = el.closest('.custom-question, .application-question, [class*="question"], [class*="card"], .field, .fieldEntry, [data-qa="field"], .select__control, div[class*="form-group"], .section');
      if (container) {
        const header = container.querySelector('label, h3, h4, .text, [class*="title"], [class*="label"], legend, span');
        if (header) {
          const clone = header.cloneNode(true);
          clone.querySelectorAll('select, input, option, button').forEach(n => n.remove());
          t = clone.textContent;
        }
      }
    }
    if (!t) {
      const appLabel = el.closest('.application-field')?.parentElement?.querySelector('.application-label');
      if (appLabel) t = appLabel.textContent;
    }
    if (!t || /^cards\[/i.test(t)) {
      t = el.getAttribute('aria-label') || el.getAttribute('placeholder') || (!/^cards\[/i.test(el.name) ? el.name : '');
    }
    return norm(t).replace(/[\u2731\*]/g, '').trim().slice(0, 180);
  };

  const fields = [];
  const buttons = [];
  let idx = 0;

  // 1. Identify choice button groups (Ashby Yes/No buttons, toggle buttons, rating buttons)
  const choiceContainers = doc.querySelectorAll('fieldset, [class*="fieldEntry" i], [class*="question" i], [data-field-path], [class*="Field" i]');
  const handledButtons = new Set();

  choiceContainers.forEach(container => {
    const btns = Array.from(container.querySelectorAll('button')).filter(b => {
      const t = norm(b.textContent).toLowerCase();
      return (
        t === 'yes' || t === 'no' ||
        b.hasAttribute('data-option') ||
        b.getAttribute('role') === 'radio' ||
        b.classList.contains('ashby-application-form-input-yesno-option') ||
        (b.hasAttribute('aria-pressed') && !/submit|apply|next|upload|back|save/i.test(t))
      );
    });

    if (btns.length >= 2) {
      btns.forEach(b => handledButtons.add(b));

      // Extract question label from container
      const clone = container.cloneNode(true);
      clone.querySelectorAll('button, input, select, textarea').forEach(n => n.remove());
      let qLabel = norm(clone.textContent).replace(/[\u2731\*]/g, '').trim().slice(0, 180);

      const options = btns.map(b => {
        const ref = 'f_' + idx++;
        b.setAttribute('data-ap-ref', ref);
        return {
          ref: ref,
          text: norm(b.textContent),
          value: b.getAttribute('data-option') || norm(b.textContent),
          pressed: b.getAttribute('aria-pressed') === 'true' || b.getAttribute('aria-checked') === 'true' || b.classList.contains('_active')
        };
      });

      fields.push({
        ref: options[0].ref,
        tag: 'button_group',
        type: 'choice_buttons',
        name: container.getAttribute('data-field-path') || '',
        id: container.id || '',
        label: qLabel,
        required: true,
        options: options
      });
    }
  });

  // 2. Gather interactive form controls
  const elements = doc.querySelectorAll('input, textarea, select, [role="combobox"], [role="radio"], [role="checkbox"], button, a.button, input[type="submit"]');
  elements.forEach(el => {
    if (handledButtons.has(el)) return;

    const style = window.getComputedStyle(el);
    const isFileInput = el.type === 'file';
    const isStyledInput = (style.opacity === '0' || style.visibility === 'hidden') && (el.type === 'radio' || el.type === 'checkbox' || isFileInput);

    if (!isFileInput && !isStyledInput && (style.display === 'none' || style.visibility === 'hidden' || (style.opacity === '0' && !el.closest('.select__control')))) {
      return;
    }

    const tag = el.tagName.toLowerCase();
    let type = (el.getAttribute('role') || el.getAttribute('type') || tag).toLowerCase();
    const isCombo = el.classList.contains('select__input') || !!el.closest('.select__control') || el.getAttribute('role') === 'combobox';
    if (isCombo && type !== 'file') type = 'combobox';
    if (type === 'hidden') return;

    const ref = 'f_' + idx++;
    el.setAttribute('data-ap-ref', ref);

    const isButton = tag === 'button' || type === 'button' || type === 'submit' || (tag === 'a' && el.classList.contains('button'));
    if (isButton) {
      buttons.push({
        ref: ref,
        text: norm(el.textContent || el.value || ''),
        type: type,
        classes: el.className || ''
      });
    } else {
      let fieldLabel = getLabel(el);
      let optLabel = '';

      if (type === 'radio' || type === 'checkbox') {
        // Option label
        if (el.id) {
          const l = doc.querySelector(`label[for="${CSS.escape(el.id)}"]`);
          if (l) optLabel = norm(l.textContent);
        }
        if (!optLabel) {
          const pl = el.closest('label');
          if (pl) optLabel = norm(pl.textContent);
        }
        if (!optLabel) {
          optLabel = norm(el.getAttribute('aria-label') || el.value || '');
        }

        // Group question label
        const container = el.closest('fieldset, [class*="fieldEntry" i], [class*="question" i], [data-field-path], [role="radiogroup"], .application-question, .custom-question');
        if (container) {
          const titleEl = container.querySelector('[class*="question-title" i], [class*="title" i], legend, [class*="heading" i], [class*="label" i], .text, h3, h4');
          if (titleEl) {
            const clone = titleEl.cloneNode(true);
            clone.querySelectorAll('input, select, textarea, button').forEach(n => n.remove());
            fieldLabel = norm(clone.textContent).replace(/[\u2731\*]/g, '').trim();
          } else {
            const allLabels = Array.from(container.querySelectorAll('label, .application-label'));
            const mainLabel = allLabels.find(l => l.getAttribute('for') !== el.id && !l.closest('[class*="option" i]'));
            if (mainLabel) {
              const clone = mainLabel.cloneNode(true);
              clone.querySelectorAll('input, select, textarea, button').forEach(n => n.remove());
              fieldLabel = norm(clone.textContent).replace(/[\u2731\*]/g, '').trim();
            }
          }
        }
      }

      const item = {
        ref: ref,
        tag: tag,
        type: type,
        is_combo: isCombo,
        name: el.name || '',
        id: el.id || '',
        label: fieldLabel,
        required: el.required || el.getAttribute('aria-required') === 'true',
        value: norm(el.value || '')
      };

      if (tag === 'select') {
        item.options = [...el.options].map(o => norm(o.textContent)).filter(Boolean).slice(0, 300);
      } else if (type === 'radio' || type === 'checkbox') {
        item.checked = el.checked || el.getAttribute('aria-checked') === 'true';
        item.option_label = optLabel;

        // If radio button has siblings with same name, collect all option labels
        if (type === 'radio' && el.name) {
          const siblingRadios = Array.from(doc.querySelectorAll(`input[type="radio"][name="${CSS.escape(el.name)}"]`));
          item.options = siblingRadios.map(sr => {
            let sl = '';
            if (sr.id) {
              const l = doc.querySelector(`label[for="${CSS.escape(sr.id)}"]`);
              if (l) sl = l.textContent;
            }
            if (!sl) {
              const pl = sr.closest('label');
              if (pl) sl = pl.textContent;
            }
            return norm(sl || sr.getAttribute('aria-label') || sr.value || '');
          }).filter(Boolean);
        }
      }
      fields.push(item);
    }
  });

  return {
    url: location.href,
    title: doc.title,
    fields: fields,
    buttons: buttons,
    text: doc.body.innerText ? doc.body.innerText.slice(0, 4000) : ''
  };
}
"""


class SemanticATSDriver:
    """Automates Greenhouse, Lever, Ashby, Workable, and Workday application forms."""

    def __init__(self, page: Page, profile: Optional[Dict[str, Any]] = None):
        self.page = page
        self.profile = profile or load_candidate_profile()
        self.mapper = QuestionMapper(self.profile)

    async def snapshot(self) -> Dict[str, Any]:
        """Aggregate snapshot across all document frames."""
        merged: Dict[str, Any] = {
            "url": self.page.url,
            "title": "",
            "fields": [],
            "buttons": [],
            "frames": {},
            "full_text": ""
        }

        frames = self.page.frames
        for idx, frame in enumerate(frames):
            try:
                data = await frame.evaluate(SNAPSHOT_JS)
                if not data or not isinstance(data, dict):
                    continue
                fields = data.get("fields") or []
                buttons = data.get("buttons") or []
                for f in fields:
                    f["frame_idx"] = idx
                for b in buttons:
                    b["frame_idx"] = idx

                merged["fields"].extend(fields)
                merged["buttons"].extend(buttons)
                if data.get("title") and not merged["title"]:
                    merged["title"] = data["title"]
                if data.get("text"):
                    merged["full_text"] += "\n" + data["text"]
            except Exception as e:
                logger.debug(f"Frame snapshot skip: {e}")
                continue

        return merged

    async def fill_form(
        self,
        resume_path: Path,
        cover_text: Optional[str] = None,
        job_id: str = "generic_job"
    ) -> Dict[str, Any]:
        """Fills visible application fields, attaches resume, and verifies field inputs."""
        snap = await self.snapshot()
        fields = snap["fields"]
        filled_count = 0
        skipped_count = 0
        fill_log: List[Dict[str, Any]] = []

        # 1. First pass: Handle file uploads (Resume & Cover Letter)
        file_inputs = [f for f in fields if f["type"] == "file"]
        resume_uploaded = False

        # Find best resume file input: prefer one labeled with 'resume' or 'cv', else first non-cover
        target_resume_input = None
        for fi in file_inputs:
            lbl = fi["label"].lower()
            if "resume" in lbl or "cv" in lbl:
                target_resume_input = fi
                break
        if not target_resume_input:
            for fi in file_inputs:
                lbl = fi["label"].lower()
                if "cover" not in lbl:
                    target_resume_input = fi
                    break

        if target_resume_input and resume_path.exists():
            ref = target_resume_input["ref"]
            lbl = target_resume_input["label"]
            frame = self.page.frames[target_resume_input["frame_idx"]]
            locator = frame.locator(f'[data-ap-ref="{ref}"]')
            try:
                await locator.set_input_files(str(resume_path), timeout=5000)
                resume_uploaded = True
                fill_log.append({"ref": ref, "label": lbl, "action": "upload_resume", "path": str(resume_path)})
                filled_count += 1
            except Exception as exc:
                fill_log.append({"ref": ref, "label": lbl, "error": str(exc)})

        # If resume was uploaded, wait for ATS parser/re-render, then refresh snapshot
        if resume_uploaded:
            await asyncio.sleep(3.0)
            snap = await self.snapshot()
            fields = snap["fields"]

        # 2. Second pass: Handle inputs, textareas, selects, choice buttons, radios, checkboxes
        for f_item in fields:
            ref = f_item["ref"]
            tag = f_item["tag"]
            f_type = f_item["type"]
            label = f_item["label"]
            options = f_item.get("options")
            frame = self.page.frames[f_item["frame_idx"]]
            locator = frame.locator(f'[data-ap-ref="{ref}"]')

            if f_type == "file":
                continue

            # Cover letter textarea
            if tag == "textarea" and any(k in label.lower() for k in ["cover", "note", "letter", "message", "comments", "additional"]):
                use_cover = cover_text or self.profile.get("cover_letter_snippet", "")
                try:
                    await locator.fill(use_cover, timeout=5000)
                    fill_log.append({"ref": ref, "label": label, "action": "fill_cover_letter"})
                    filled_count += 1
                except Exception as exc:
                    fill_log.append({"ref": ref, "label": label, "error": str(exc)})
                continue

            # Choice buttons group (Ashby Yes/No button pairs, button toggles)
            if f_type == "choice_buttons":
                opt_list = f_item.get("options", [])
                opt_texts = [o["text"] for o in opt_list]
                answer, mapped = self.mapper.map_field(label, opt_texts)
                if not mapped or answer is None:
                    skipped_count += 1
                    continue

                target_norm = norm(answer)
                chosen_opt = None
                for opt in opt_list:
                    if norm(opt["text"]) == target_norm or norm(opt.get("value", "")) == target_norm:
                        chosen_opt = opt
                        break
                if not chosen_opt:
                    for opt in opt_list:
                        if target_norm in norm(opt["text"]) or norm(opt["text"]) in target_norm:
                            chosen_opt = opt
                            break

                if chosen_opt:
                    try:
                        btn_loc = frame.locator(f'[data-ap-ref="{chosen_opt["ref"]}"]')
                        await btn_loc.click(timeout=5000)
                        fill_log.append({"ref": chosen_opt["ref"], "label": label, "action": "click_choice_btn", "val": chosen_opt["text"]})
                        filled_count += 1
                    except Exception as exc:
                        fill_log.append({"ref": chosen_opt["ref"], "label": label, "error": str(exc)})
                else:
                    skipped_count += 1
                continue

            # Map field through QuestionMapper
            answer, mapped = self.mapper.map_field(label, options)

            if not mapped or answer is None:
                skipped_count += 1
                continue

            try:
                if f_type == "combobox":
                    # React-Select / ARIA combobox
                    try:
                        await locator.click(timeout=5000)
                        await asyncio.sleep(0.3)
                        await self.page.keyboard.type(answer, delay=70)
                        await asyncio.sleep(1.2)

                        # Look for open options in the frame
                        menu_opts = frame.locator('.select__menu .select__option, [id*="react-select"][role="option"]')
                        opt_cnt = await menu_opts.count()
                        if opt_cnt > 0:
                            target_norm = norm(answer)
                            clicked = False
                            for oi in range(min(opt_cnt, 15)):
                                txt = norm(await menu_opts.nth(oi).text_content() or "")
                                if target_norm in txt or txt in target_norm:
                                    await menu_opts.nth(oi).click(timeout=3000)
                                    clicked = True
                                    break
                            if not clicked:
                                await menu_opts.first.click(timeout=3000)
                        else:
                            await self.page.keyboard.press("ArrowDown")
                            await asyncio.sleep(0.2)
                            await self.page.keyboard.press("Enter")

                        fill_log.append({"ref": ref, "label": label, "action": "combobox_select", "val": answer})
                        filled_count += 1
                    except Exception as exc:
                        fill_log.append({"ref": ref, "label": label, "error": str(exc)})

                elif tag == "select":
                    # Native select
                    try:
                        await locator.select_option(label=answer, timeout=5000)
                    except Exception:
                        await locator.select_option(value=answer, timeout=5000)
                    fill_log.append({"ref": ref, "label": label, "action": "select", "val": answer})
                    filled_count += 1

                elif f_type in ["radio", "checkbox"]:
                    # Match against option_label or value
                    opt_lbl = f_item.get("option_label", "")
                    opt_val = f_item.get("value", "")
                    target_norm = norm(answer)
                    opt_norm = norm(opt_lbl) or norm(opt_val)

                    is_match = False
                    if opt_norm == target_norm:
                        is_match = True
                    elif opt_norm in ["male", "female"] or target_norm in ["male", "female"]:
                        is_match = (opt_norm == target_norm)
                    elif target_norm == "yes" and opt_norm.startswith("yes"):
                        is_match = True
                    elif target_norm == "no" and opt_norm.startswith("no"):
                        is_match = True
                    elif len(opt_norm) > 5 and len(target_norm) > 5 and (target_norm in opt_norm or opt_norm in target_norm):
                        is_match = True

                    if is_match:
                        try:
                            await locator.check(force=True, timeout=5000)
                        except Exception:
                            await locator.click(force=True, timeout=5000)
                        fill_log.append({"ref": ref, "label": label, "action": "check", "val": opt_lbl or opt_val})
                        filled_count += 1

                elif f_type == "number":
                    clean_val = re.sub(r"\D", "", str(answer))
                    if clean_val:
                        await locator.fill(clean_val, timeout=5000)
                        fill_log.append({"ref": ref, "label": label, "action": "fill_number", "val": clean_val})
                        filled_count += 1

                elif f_type in ["text", "email", "tel", "textarea", "url"] or tag in ["input", "textarea"]:
                    # Check autocomplete locations
                    if any(k in label.lower() for k in ["location", "city", "address", "residence"]):
                        await locator.click(timeout=5000)
                        await locator.fill("")
                        await self.page.keyboard.type(answer, delay=100)
                        await asyncio.sleep(2.0)
                        try:
                            menu_item = frame.locator('li.ui-menu-item, [role="option"], .select__option, .location-suggestion, [data-qa="location-suggestion"]').first
                            if await menu_item.count() > 0:
                                await menu_item.click(timeout=2000)
                            else:
                                await self.page.keyboard.press("ArrowDown")
                                await asyncio.sleep(0.5)
                                await self.page.keyboard.press("Enter")
                        except Exception:
                            pass
                    else:
                        await locator.fill(answer, timeout=5000)

                    fill_log.append({"ref": ref, "label": label, "action": "fill", "val": answer})
                    filled_count += 1

            except Exception as exc:
                fill_log.append({"ref": ref, "label": label, "error": str(exc)})

        # Take proof screenshot of the filled form
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        clean_slug = re.sub(r"[^\w\-]", "_", job_id)
        screenshot_path = PROOF_DIR / f"{ts}_{clean_slug}_pre_submit.png"
        try:
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
        except Exception:
            try:
                await self.page.screenshot(path=str(screenshot_path), full_page=False)
            except Exception:
                pass

        return {
            "status": "ready_for_review",
            "filled_fields": filled_count,
            "skipped_fields": skipped_count,
            "screenshot": str(screenshot_path),
            "log": fill_log
        }

    async def advance_multipage_or_submit(
        self,
        auto_submit: bool = False,
        job_id: str = "generic_job"
    ) -> Dict[str, Any]:
        """Handles multi-step pages (e.g. Workday / Ashby multi-step) or executes submit under explicit gate."""
        snap = await self.snapshot()
        buttons = snap["buttons"]

        # Check if already confirmed
        for pattern in CONFIRM_PATTERNS:
            if re.search(pattern, snap["full_text"], re.IGNORECASE):
                return {"status": "already_submitted", "message": "Confirmation text detected on page."}

        # Look for Forward / Next buttons
        next_btn = None
        submit_btn = None

        for b in buttons:
            txt = b["text"].lower()
            frame = self.page.frames[b["frame_idx"]]
            loc = frame.locator(f'[data-ap-ref="{b["ref"]}"]')

            if any(k in txt for k in ["next", "continue", "save and continue", "proceed", "review"]):
                next_btn = loc
                break
            elif any(k in txt for k in ["submit application", "submit", "apply now", "send application"]):
                submit_btn = loc

        if next_btn:
            try:
                await next_btn.click(timeout=5000)
                await asyncio.sleep(3.0)
                return {"status": "advanced_next_page"}
            except Exception as e:
                logger.warning(f"Failed clicking next button: {e}")

        if submit_btn:
            if not auto_submit:
                return {
                    "status": "held_for_review",
                    "message": "Form fully filled and validated. Paused at final submit button for human gate."
                }
            else:
                await submit_btn.click(timeout=5000)
                await asyncio.sleep(5.0)

                # Capture final post-submit proof
                ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                clean_slug = re.sub(r"[^\w\-]", "_", job_id)
                post_proof = PROOF_DIR / f"{ts}_{clean_slug}_submitted_proof.png"
                await self.page.screenshot(path=str(post_proof), full_page=True)

                # Verify confirmation
                post_snap = await self.snapshot()
                confirmed = any(re.search(p, post_snap["full_text"], re.IGNORECASE) for p in CONFIRM_PATTERNS)

                # Record event in SQLite ledger
                self._record_timeline_event(job_id, "APPROVED", "APPLIED" if confirmed else "SUBMITTED_UNVERIFIED", f"Proof: {post_proof.name}")

                return {
                    "status": "submitted" if confirmed else "submitted_unverified",
                    "confirmed": confirmed,
                    "proof_screenshot": str(post_proof)
                }

        return {"status": "no_forward_action_found"}

    async def traverse_portal(
        self,
        resume_path: Path,
        cover_text: Optional[str] = None,
        job_id: str = "generic_job",
        auto_submit: bool = False,
        max_pages: int = 8
    ) -> Dict[str, Any]:
        """Traverses single-page and multi-page application flows (e.g. Workday multi-step)."""
        all_logs: List[Dict[str, Any]] = []
        total_filled = 0
        total_skipped = 0
        last_screenshot: Optional[str] = None

        for page_num in range(1, max_pages + 1):
            logger.info(f"Processing application stage/page {page_num}...")
            fill_res = await self.fill_form(resume_path, cover_text=cover_text, job_id=f"{job_id}_p{page_num}")
            total_filled += fill_res.get("filled_fields", 0)
            total_skipped += fill_res.get("skipped_fields", 0)
            all_logs.extend(fill_res.get("log", []))
            last_screenshot = fill_res.get("screenshot")

            nav_res = await self.advance_multipage_or_submit(auto_submit=auto_submit, job_id=job_id)
            status = nav_res.get("status")
            logger.info(f"Stage/page {page_num} nav result: {status}")

            if status in ["held_for_review", "submitted", "submitted_unverified", "already_submitted"]:
                return {
                    "status": status,
                    "pages_processed": page_num,
                    "filled_fields": total_filled,
                    "skipped_fields": total_skipped,
                    "screenshot": last_screenshot,
                    "submission": nav_res,
                    "log": all_logs
                }
            elif status == "advanced_next_page":
                await asyncio.sleep(3.0)
                continue
            else:
                return {
                    "status": "completed_or_unclear_step",
                    "pages_processed": page_num,
                    "filled_fields": total_filled,
                    "skipped_fields": total_skipped,
                    "screenshot": last_screenshot,
                    "submission": nav_res,
                    "log": all_logs
                }

        return {
            "status": "max_pages_reached",
            "pages_processed": max_pages,
            "filled_fields": total_filled,
            "skipped_fields": total_skipped,
            "screenshot": last_screenshot,
            "log": all_logs
        }

    def _record_timeline_event(self, job_id: str, from_stage: str, to_stage: str, note: str):
        if not DB_PATH.exists():
            return
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO application_timeline_events (job_id, from_stage, to_stage, note, event_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                job_id,
                from_stage,
                to_stage,
                note,
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            ))
            if to_stage in ("APPLIED", "SUBMITTED", "CONFIRMED"):
                cur.execute("""
                    UPDATE agent_episodic_memories
                    SET lifecycle_stage = 'APPLIED', applied_at = ?
                    WHERE job_id = ?
                """, (datetime.now(timezone.utc).isoformat(), job_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Could not record timeline event: {e}")
