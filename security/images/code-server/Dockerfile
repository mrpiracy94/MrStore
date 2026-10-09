# Explicitly patch only the two packages Trivy located inside LSIO code-server.
# Preserve the complete LinuxServer init, UID mapping, 8443 port, /config and /workspace.
FROM node:22-alpine AS fixed-node-packages
RUN npm install --prefix /opt/patched --ignore-scripts --omit=dev --no-audit --no-fund \
      shell-quote@1.11.0 basic-ftp@6.2.1

FROM lscr.io/linuxserver/code-server:latest
RUN test -f /app/code-server/lib/vscode/node_modules/shell-quote/package.json \
 && test -f /app/code-server/node_modules/basic-ftp/package.json \
 && rm -rf /app/code-server/lib/vscode/node_modules/shell-quote \
           /app/code-server/node_modules/basic-ftp
COPY --from=fixed-node-packages /opt/patched/node_modules/shell-quote/ /app/code-server/lib/vscode/node_modules/shell-quote/
COPY --from=fixed-node-packages /opt/patched/node_modules/basic-ftp/ /app/code-server/node_modules/basic-ftp/
