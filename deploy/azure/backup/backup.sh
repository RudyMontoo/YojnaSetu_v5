#!/usr/bin/env bash
# Nightly Mongo backup: dump the whole DB and upload a single gzipped archive to
# a private Azure Blob container via a write-only SAS. Atlas M0 has no automated
# backups, so this is the data-loss insurance — one bad delete/migration and the
# newest nightly archive is the restore point.
#
# Restore (manually, when needed):
#   az storage blob download --account-name <SA> -c mongo-backups -n <file> -f dump.gz --sas-token '<read-sas>'
#   mongorestore --uri="<MONGODB_URI>" --archive=dump.gz --gzip --drop
#
# Env (set by the Job, from .env.deploy):
#   MONGODB_URI        Atlas SRV connection string (secret)
#   BACKUP_BLOB_BASE   https://<acct>.blob.core.windows.net/mongo-backups
#   BACKUP_SAS         container SAS (create+write), no leading '?'  (secret)
set -euo pipefail

: "${MONGODB_URI:?MONGODB_URI not set}"
: "${BACKUP_BLOB_BASE:?BACKUP_BLOB_BASE not set}"
: "${BACKUP_SAS:?BACKUP_SAS not set}"

TS="$(date -u +%Y%m%d-%H%M%S)"
NAME="yojnasetu-${TS}.archive.gz"
FILE="/tmp/${NAME}"

echo "[BACKUP] $(date -u) starting mongodump -> ${NAME}"
mongodump --uri="${MONGODB_URI}" --archive="${FILE}" --gzip
SIZE="$(stat -c%s "${FILE}")"
echo "[BACKUP] dump complete: ${SIZE} bytes"

# Put Blob (single request). Gzipped M0 dumps are small; well within the limit.
URL="${BACKUP_BLOB_BASE}/${NAME}?${BACKUP_SAS}"
echo "[BACKUP] uploading to blob…"
curl -sS -f -X PUT -T "${FILE}" \
  -H "x-ms-blob-type: BlockBlob" \
  -H "Content-Type: application/gzip" \
  "${URL}"
echo "[BACKUP] $(date -u) uploaded ${NAME} (${SIZE} bytes) — done"
