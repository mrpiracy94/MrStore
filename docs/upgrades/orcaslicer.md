# OrcaSlicer: restore Docker default seccomp

## Scope
Remove `security_opt: [seccomp:unconfined]` from the LinuxServer OrcaSlicer container. This restricts syscalls but does **not** patch the vulnerable image or justify publishing it. Keep the app quarantined until complete AMD64 and ARM64 image scans each show zero HIGH and CRITICAL findings and actual ZimaOS compatibility is confirmed.

## Backup
Stop OrcaSlicer. Back up `/DATA/AppData/orcaslicer/config` to a separate protected location and verify the archive can be read. Record current image digest and Compose configuration before changing security settings.

## Migration
No data or port migration. Keep image, PUID, PGID, `/config`, ports 3000 and 3001, and shared-memory size unchanged. Recreate the container without `seccomp:unconfined` only in a controlled test environment.

## Verification
Run Compose syntax validation and security checks. On AMD64 and ARM64, start the container and test browser access, loading projects, slicing and exporting files, saving/reopening configuration, and logs for seccomp-denied syscalls. Run complete image CVE scans on both architectures; require 0 HIGH and 0 CRITICAL to release. CI syntax tests alone do not prove runtime compatibility.

## Rollback
If the GUI or slicer fails, stop the test container, restore the previous Compose file and pinned image digest, and restore `/config` from the verified backup if needed. Do not publish the less-confined configuration as a security workaround; leave the app quarantined pending a compatible fix.
