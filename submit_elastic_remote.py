"""Keep the former Elastic submit flow disabled until every required answer is verified."""


def main() -> None:
    print(
        "Skipped: the saved Elastic form contains unsupported answers for work "
        "authorization, sponsorship, certification, travel, and pronouns. No "
        "page was opened, no resume was uploaded, and no email OTP was accessed. "
        "Review the real posting and every required answer before applying."
    )


if __name__ == "__main__":
    main()
