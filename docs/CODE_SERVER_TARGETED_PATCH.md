# Code Server — targeted Node.js dependency remediation

The MrStore LinuxServer Code Server image reported the following in its bundled
Node.js dependencies, identified by Trivy (PR #43):

| Severity | Package | Existing | Patched | Exact path |
|---|---|---|---|---|
| CRITICAL | shell-quote | 1.10.0 | 1.11.0 | `/app/code-server/lib/vscode/node_modules/shell-quote` |
| HIGH | basic-ftp | 5.3.1 | 6.2.1 | `/app/code-server/node_modules/basic-ftp` |

The Dockerfile `security/images/code-server/Dockerfile` copies **only these
specific updated packages**, from a disposable npm builder, into the **same
LinuxServer container**. It does not replace Code Server, its service manager,
port 8443, UID/GID settings, or persistent paths `/config` and `/workspace`.

The verification workflow tests both architectures with Trivy, boots disposable
containers to verify HTTP and both volumes, and exercises the patched `basic-ftp`
client against a real **temporary local FTP server**.

**Compatibility warning:** basic-ftp v6 changes its default behavior to block
FTP bounce attacks through separate transfer hosts. If an organization relies
on unusual FTP servers requiring different data-host endpoints, review/test
that integration before installing the new image; a normal FTP listing test is
not a substitute for testing all existing workflows.

Once a release is successfully published, the catalog can be changed in an
independent PR to reference the **immutable multiarch digest**. Existing ZimaOS
Code Server data should be backed up before upgrading:

- `/DATA/AppData/code-server/config`
- `/DATA/Workspace`

Scanner findings refer to reported vulnerabilities only, not a guarantee that
no issues exist. A code-server upstream update may require a new targeted build
and re-verification. Never use this image as a blanket replacement for other
LinuxServer apps.

Upstream advisory: https://github.com/advisories/GHSA-pqg4-j6r4-53mv
FTP upstream releases: https://github.com/patrickjuchli/basic-ftp/releases
