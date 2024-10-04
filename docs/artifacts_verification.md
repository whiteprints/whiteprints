<!--
SPDX-FileCopyrightText: © 2024 Romain Brault <mail@romainbrault.com>

SPDX-License-Identifier: GPL-3.0-or-later
-->

# 🛡️ Verifying Release Artifacts

You can verify the authenticity of release artifacts using [cosign]. To do so, run the following command:

```console
cosign verify-blob \
    --new-bundle-format \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
    --certificate-identity-regexp="^https://github.com/whiteprints/whiteprints/.github/workflows/upload_artifacts.yml?" \
    --bundle <path_to_the_artifact>.sigstore.json \
    <path_to_the_artifact>
```

Where:

  - `<path_to_the_artifact>` is the path to the artifact you want to verify.
  - `<path_to_the_artifact>.sigstore.json` is the path to the sigstore
    signature associated with the artifact.

For more details on [cosign] and [sigstore], refer to their official
documentation.

[cosign]: https://docs.sigstore.dev/cosign/
[sigstore]: https://www.sigstore.dev/
