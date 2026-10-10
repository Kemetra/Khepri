#!/usr/bin/env bash
# Scan a locally built image for advisories, with no registry and no push (SCRUM-41).
#
# The only image scan Khepri had was ECR scan-on-push, which ran only after a publish that needs
# three unset repository variables, so it never ran (SCRUM-39, finding X1). This scans the image
# the job just built in the local Docker daemon instead.
#
# Gate: a HIGH or CRITICAL advisory that has a fixed version. `--ignore-unfixed` drops the ones
# nobody can act on yet; the base image carries hundreds of those at MEDIUM and below.
# Exceptions: `.github/advisories/trivyignore.yaml`, checked by `advisory_exceptions.py`.
#
# Trivy is downloaded from its GitHub release and verified against the SHA-256 below, the same
# way every action here is pinned by commit, so a re-pointed tag or a replaced asset fails the
# check instead of running. Trivy's advisory database is not pinnable; its version and update
# time are printed with the findings.
#
#   scan_image.sh <local-image> [report.json]
#
# Exits 0 (nothing blocking), 1 (a blocking advisory) or 2 (the scanner failed, or could not
# fail on the canary). Run it from the repository root.
set -uo pipefail

image="${1:?usage: scan_image.sh <local-image> [report.json]}"
report="${2:-image-advisories.json}"

TRIVY_VERSION="0.74.0"
TRIVY_SHA256="2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a"
IGNOREFILE=".github/advisories/trivyignore.yaml"
# Trivy returns 1 for its own errors, so findings get a code of their own.
FOUND=3

summary="${GITHUB_STEP_SUMMARY:-/dev/null}"
bin_dir="${RUNNER_TEMP:-/tmp}/trivy-${TRIVY_VERSION}"

install_trivy() {
  local archive="${bin_dir}/trivy.tar.gz"
  mkdir -p "${bin_dir}" &&
    curl -sSfL -o "${archive}" \
      "https://github.com/aquasecurity/trivy/releases/download/v${TRIVY_VERSION}/trivy_${TRIVY_VERSION}_Linux-64bit.tar.gz" &&
    echo "${TRIVY_SHA256}  ${archive}" | sha256sum --check --strict - &&
    tar -xzf "${archive}" -C "${bin_dir}" trivy
}

if ! install_trivy; then
  echo "FAIL: could not install the pinned Trivy ${TRIVY_VERSION}" >&2
  exit 2
fi
trivy="${bin_dir}/trivy"
gate=(--skip-version-check --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed
  --ignorefile "${IGNOREFILE}" --exit-code "${FOUND}")

# The gate must be able to fail. The same flags, database and exceptions must block the
# known-vulnerable canary lock (urllib3 1.26.4) before a clean image result means anything.
# Trivy recognises a lockfile only by the name `uv.lock`, so the canary is scanned as a copy.
canary_dir="$(mktemp -d)"
cp .github/advisories/known-vulnerable.uv.lock "${canary_dir}/uv.lock"
canary=0
"${trivy}" fs --quiet "${gate[@]}" "${canary_dir}/uv.lock" > /dev/null || canary=$?
if [ "${canary}" -ne "${FOUND}" ]; then
  echo "FAIL: the gate did not block the known-vulnerable canary (trivy exited ${canary})" >&2
  exit 2
fi
echo "the gate blocks the known-vulnerable canary"

status=0
"${trivy}" image "${gate[@]}" --format json --output "${report}" "${image}" || status=$?

if [ "${status}" -ne 0 ] && [ "${status}" -ne "${FOUND}" ]; then
  echo "FAIL: trivy exited ${status} while scanning ${image}; nothing was gated" >&2
  exit 2
fi

table="$("${trivy}" convert --skip-version-check --format table "${report}")"
{
  echo "### Image advisories: \`${image}\`"
  echo
  echo "Gate: HIGH or CRITICAL with a fixed version. Exceptions: \`${IGNOREFILE}\`."
  echo
  echo '```text'
  "${trivy}" version
  echo
  echo "${table}"
  echo '```'
} | tee -a "${summary}"

if [ "${status}" -eq "${FOUND}" ]; then
  echo "FAIL: ${image} carries a fixable HIGH or CRITICAL advisory (table above)" >&2
  exit 1
fi
echo "${image}: no fixable HIGH or CRITICAL advisory"
