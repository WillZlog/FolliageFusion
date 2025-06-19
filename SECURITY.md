# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project (e.g., credential leakage, directory traversal, data exposure), please contact the maintainer immediately:

- **Email**: [williamalbinze@gmail.com]
- **GitHub Issues**: Please avoid opening public issues for sensitive security concerns.

All reports will be reviewed and responded to promptly. Responsible disclosure is appreciated.

## Security Practices

This project follows these practices:
- `.env`, `auth.db`, and other sensitive files are ignored via `.gitignore`
- Secrets and keys are stored securely using environment variables
- History is cleaned with `git filter-repo` if leaks are detected
- Proxy credentials and IPs are never stored in code

## Suggestions

If you have ideas for improving security (e.g., input sanitization, authentication improvements), please feel free to open a non-sensitive issue or pull request.

Thank you for helping keep this project secure!
