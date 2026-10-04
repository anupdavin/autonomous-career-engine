"""Skip an Appfire posting that is remote only from Poland."""


def main() -> None:
    print(
        "Skipped: this Appfire role is remote only within Poland, while the "
        "active search requires remote roles eligible from India. No page was "
        "opened, no resume was uploaded, and no email OTP was accessed."
    )


if __name__ == "__main__":
    main()
