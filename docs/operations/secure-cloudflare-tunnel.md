# Secure Cloudflare Tunnel and Private Access Runbook

This runbook defines the architecture, deployment, and emergency control procedures for remote access to the local Project 1 command center. It uses a remotely managed named Cloudflare Tunnel paired with Cloudflare Zero Trust Access.

> [!IMPORTANT]
> This document uses placeholders only. No live tunnel, DNS record, Access policy, or account setting is created or activated by this runbook.

---

## 1. Core Architecture and Security Invariants

### Architecture Flow

```
[Operator Browser]
        |
        v HTTPS (TLS 1.3)
[Cloudflare Edge Network]
  - Zero Trust Access Application (Default-Deny Policy)
  - Include: [APPROVED_IDENTITY_OR_GROUP]
  - Require: [POSTURE_POLICY]
  - Edge generates signed Cf-Access-Jwt-Assertion
        |
        v Remotely Managed Cloudflare Tunnel (Outbound Quic/HTTP2 over TLS)
[Windows Host Machine]
  - cloudflared daemon running as Windows Service
  - Local egress to loopback interface only
        |
        v HTTP (Local Loopback)
[app_server.py (127.0.0.1:8080)]
  - Bound strictly to 127.0.0.1:8080 (never 0.0.0.0)
  - Pure ASGI Host header filtering (APP_ALLOWED_HOSTS=[HOSTNAME])
  - Origin and CSRF validation on all unsafe methods outside GET, HEAD, and OPTIONS (APP_ALLOWED_ORIGINS=https://[HOSTNAME])
  - Double-submit CSRF protection (app_csrf cookie with SameSite=Strict and Secure)
  - Curated operational field whitelist (no raw resumes, pitches, or credentials)
  - Material preparation local only (application submission remains human-controlled)
```

### Critical Invariants

1. **Access Application Exists Before Publishing**: The Cloudflare Access self-hosted application must be fully configured and active before routing DNS or publishing the tunnel. Never expose the origin hostname without active Access enforcement.
2. **Strict Loopback Binding**: `app_server.py` binds strictly to `127.0.0.1:8080`. It must never bind to `0.0.0.0` or any LAN-facing interface.
3. **Default-Deny Access Policy**: All traffic is denied by default. Access is granted only when the incoming request satisfies the approved identity Include rule and all required posture Require rules.
4. **Origin Access JWT Validation Boundary**: app_server.py implements Host, Origin, and CSRF checks, but it does not validate Cloudflare Access JWTs. The Cloudflare Tunnel connector/origin configuration performs the Access JWT signature and audience checks before traffic reaches the local loopback interface.
5. **No Ad-Hoc Quick Tunnels**: Quick tunnels (*.trycloudflare.com) are prohibited because they bypass Access policies and expose endpoints publicly.
6. **Zero Inbound Ports**: Router and firewall configurations require zero inbound open ports. All tunnel traffic is outbound.
7. **Human-Controlled Submissions**: Application material preparation (/api/prepare-materials) is local; submission to job boards remains 100% human-controlled.

---

## 2. Placeholders Reference

All configuration values and policy selectors are represented by the following placeholders:

- `[APPROVED_IDENTITY_OR_GROUP]`: Approved operator identity or directory group
- `[TEAM_NAME]`: Cloudflare Zero Trust organization team name
- `[POSTURE_POLICY]`: Enforced corporate device posture policy rule
- `[HOSTNAME]`: Fully qualified domain name routed to the command center
- `[TUNNEL_ID]`: Unique identifier for the named Cloudflare Tunnel
- `[AUD_TAG]`: Cloudflare Access Application Audience Tag

---

## 3. Cloudflare Access Configuration (Step 1: Edge Security First)

The Access application must exist before the tunnel publishes the route.

### 1. Create Self-Hosted Access Application
1. In the Cloudflare Zero Trust dashboard, navigate to **Access** > **Applications** > **Add an application**.
2. Select **Self-hosted**.
3. Application Configuration:
   - Application Name: `Project 1 Operator Command Center`
   - Application Domain: `[HOSTNAME]`
   - Session Duration: Configured according to security requirements
4. Copy the Application Audience Tag and record it as `[AUD_TAG]`.

### 2. Configure Default-Deny Access Policy
Create a policy with action **Allow** under a default-deny posture:
- **Include Rule**:
  - Identity selector specifying `[APPROVED_IDENTITY_OR_GROUP]`
- **Require Rule (Device Posture)**:
  - Posture selector specifying `[POSTURE_POLICY]`

Requests lacking valid identity credentials or failing device posture checks are blocked at Cloudflare edge.

---

## 4. Remotely Managed Cloudflare Tunnel Configuration

A remotely managed tunnel is created and managed directly in the Cloudflare Zero Trust dashboard.

### 1. Create Named Tunnel in Dashboard
1. Go to **Networks** > **Tunnels** > **Create a tunnel**.
2. Select **Cloudflare** (remotely managed).
3. Name the tunnel and record `[TUNNEL_ID]`.

### 2. Configure Public Hostname Routing
Under the tunnel's **Public Hostname** tab, add a route:
- Public Hostname: `[HOSTNAME]`
- Service Type: `HTTP`
- URL: `127.0.0.1:8080`
- Additional Settings:
  - Connect Timeout: `15s`
  - HTTP2 Origin: Disabled (Cloudflare requires an HTTPS origin for HTTP2 origin connections; keep disabled for this plain HTTP loopback setup, and enable only if the origin is changed to HTTPS)

Add a catch-all service rule routing unmatched paths to `http_status:404`.

### 3. Install Connector on Windows Host
Run this procedure in an elevated PowerShell session (Administrator). Using a secure prompt avoids putting the token into shell command history or persistent files. The install process receives the token as a transient command-line argument during execution, which local process inspection or process-creation auditing on the host could observe while the installer runs. Session variables are immediately removed after execution:

```powershell
# Prompt interactively for the connector token as a masked secure string
$secureToken = Read-Host -Prompt "Enter Cloudflare Tunnel connector token" -AsSecureString

# Convert in memory, install the Windows service, and clear variables immediately
$plainToken = [System.Net.NetworkCredential]::new("", $secureToken).Password
cloudflared service install $plainToken
Remove-Variable secureToken, plainToken

# Start and verify the Windows service
Start-Service cloudflared
Get-Service cloudflared
```

---

## 5. Host Application Environment Configuration

Configure the local application server environment variables before launching `app_server.py`:

```powershell
# Allowed host header for reverse proxy ingress (comma-separated if multiple)
$env:APP_ALLOWED_HOSTS = "[HOSTNAME]"

# Allowed origin for CSRF and all unsafe methods outside GET, HEAD, and OPTIONS
$env:APP_ALLOWED_ORIGINS = "https://[HOSTNAME]"

# Require Secure attribute on app_csrf cookie
$env:APP_CSRF_COOKIE_SECURE = "true"

# Start local server bound strictly to loopback
python app_server.py
```

### Server Invariants
- Listener host: `127.0.0.1` (never `0.0.0.0`).
- Listener port: `8080`.
- ASGI Middleware:
  - Host authorization checks raw `Host` header against loopback and `APP_ALLOWED_HOSTS`. Fails closed on malformed host syntax and invalid ports. Bracketed IPv6 values are validated with ipaddress and normalized. Forwarded headers (`X-Forwarded-Host`) are ignored.
  - All unsafe HTTP methods (every method outside `GET`, `HEAD`, and `OPTIONS`) require an exact allowed `Origin` and matching `app_csrf` cookie + `X-CSRF-Token` header.
  - `GET /` issues `app_csrf` cookie with `Path=/` and `SameSite=Strict` (plus `Secure` when `APP_CSRF_COOKIE_SECURE=true`) only after Host authorization passes.

---

## 6. Cloudflare Access JWT Validation Boundary

The security boundary between Cloudflare Tunnel and the local application is explicitly divided:

1. **Application Server Scope**: `app_server.py` implements Host filtering, Origin validation, and CSRF double-submit token checks on all methods outside `GET`, `HEAD`, and `OPTIONS`. It does not validate Cloudflare Access JWTs.
2. **Connector Origin Validation Scope**: The Cloudflare Tunnel connector/origin configuration performs the Access JWT signature and audience checks before proxying requests to loopback:
   - **Local-Managed Configuration Equivalent**:
     In `config.yml`, configure under `originRequest`:
     ```yaml
     originRequest:
       access:
         required: true
         teamName: "[TEAM_NAME]"
         audTag:
           - "[AUD_TAG]"
     ```
   - **Remotely Managed Dashboard Configuration**:
     Configure and verify the equivalent connector origin Access validation setting in the Cloudflare Zero Trust dashboard under the public hostname origin configuration.
   - **Failsafe Inactive Policy**: If connector-level origin Access validation is unavailable in the remotely managed configuration, keep the tunnel inactive pending a supported setup.
3. **No Direct Trust in Headers**: Do not imply or rely on the Python application validating JWTs directly. Client-supplied `Cf-Access-Jwt-Assertion` headers must never be trusted without cryptographic verification by the tunnel connector ingress layer.

---

## 7. Operational Verification

Execute these verification checks:

1. **Direct Loopback Verification**:
   ```powershell
   curl -Uri "http://127.0.0.1:8080/api/system" -UseBasicParsing
   ```
   Confirm HTTP 200 response with status `ready` or `idle`.

2. **Access Denial Check**:
   Navigate to `https://[HOSTNAME]` from an unauthenticated browser or unauthorized identity. Confirm access is denied at Cloudflare edge.

3. **Authorized Login Check**:
   Authenticate with `[APPROVED_IDENTITY_OR_GROUP]` and device satisfying `[POSTURE_POLICY]`. Confirm dashboard loads.

4. **CSRF Enforcement Check**:
   Verify POST requests to `/api/transition` without `X-CSRF-Token` or with mismatched token return HTTP 403 Forbidden.

---

## 8. Emergency Procedures & Killswitch

If suspicious activity occurs or access needs immediate termination:

### Level 1: Terminate Host Service (Immediate Local Sever)
Stops outbound tunnel connectivity immediately from the Windows host:
```powershell
Stop-Service cloudflared
```

### Level 2: Lock Access Policy (Edge Block)
In Cloudflare Zero Trust:
1. Navigate to **Access** > **Applications** > `Project 1 Operator Command Center`.
2. Change the policy action from **Allow** to **Block** for all users, or toggle the application status to **Disabled**.

### Level 3: Remove Public Hostname Route (Edge Sever)
In the Zero Trust dashboard under **Networks** > **Tunnels**:
Delete the public hostname route for `[HOSTNAME]`.

### Level 4: Delete Tunnel Credentials (Full Revocation)
Delete the tunnel from Cloudflare Zero Trust and remove the service configuration from the Windows host:
```powershell
cloudflared service uninstall
```
