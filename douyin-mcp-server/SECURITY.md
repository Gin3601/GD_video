# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x.x   | :white_check_mark: |
| < 2.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly:

1. **Do NOT** open a public GitHub issue for security vulnerabilities
2. Send an email to the maintainers with details of the vulnerability
3. Include steps to reproduce the issue
4. Allow reasonable time for the maintainers to respond and fix the issue

## Security Best Practices for Users

### Cookie Security

This project stores Douyin login cookies locally. Please follow these guidelines:

- **Never share** `douyin-cookies.json` file
- **Never commit** cookie files to version control
- Store cookie files in a secure location with appropriate permissions
- Regularly rotate your login credentials

### Environment Security

- Run this tool only on trusted machines
- Keep Node.js and dependencies up to date
- Review the code before running on sensitive systems

## Known Security Considerations

1. **Browser Automation**: This project uses Puppeteer for browser automation. The browser runs with some security features disabled to bypass automation detection. Use only in controlled environments.

2. **Cookie Storage**: Login credentials are stored in plain JSON. Consider encrypting sensitive data in production environments.

3. **Network Traffic**: The tool connects to douyin.com. Ensure you're on a secure network.

## Dependency Security

This project uses automated dependency updates. To check for vulnerabilities:

```bash
cd mcp-server
npm audit
```

## Contact

For security concerns, please contact the repository maintainers.
