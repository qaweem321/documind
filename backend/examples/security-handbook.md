# Security Handbook

Everyone at Northwind Labs is responsible for keeping customer data safe. This handbook lists the rules every
employee and contractor must follow.

## Accounts and passwords

Use the company password manager for every work account, and turn on two-factor authentication everywhere it
is offered. Hardware security keys are required for the admin console, the cloud provider and GitHub. Never
share passwords, even with your manager or IT. IT will never ask for your password.

## Devices

Company laptops must have full-disk encryption and automatic updates turned on, and lock after five minutes
of inactivity. Install software only from the company software catalog or official vendor websites. Personal
phones may be used for work email and chat if they have a screen lock and are updated to a supported OS
version.

## Customer data

Customer data stays in production systems. Don't copy it to your laptop, spreadsheets or personal storage. If
you need data for debugging, use the anonymized staging database. Access to production databases requires an
approved access request and expires after 24 hours.

## Reporting incidents

If you think something went wrong, for example a lost laptop, a phishing email you clicked, or data sent to
the wrong customer, report it in the #security-incidents channel or to security@northwindlabs.example
within one hour. You won't get in trouble for reporting a mistake; hiding one is a serious problem.

Lost or stolen devices are wiped remotely, so report them even if you think they will turn up.
