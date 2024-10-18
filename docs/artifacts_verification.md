<!--
SPDX-FileCopyrightText: © 2024 The "Whiteprints" contributors <whiteprints@pm.me>

SPDX-License-Identifier: CC-BY-NC-SA-4.0
-->

# 🛡️ Verifying Release Artifacts

All release artifact are provided with a [build attestation].

Verify the integrity and provenance of an artifact using its associated cryptographically signed attestations.

You can verify an attestation with the [GitHub command line](https://cli.github.com/manual/gh_attestation_verify) by running:

```console
gh attestation verify <path_to_the_release_artifact> --repo whiteprints/whiteprints
```


You also can verify the authenticity of release artifacts using [cosign]. To do so, run the following command:

```console
cosign verify-blob \
    --new-bundle-format \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
    --certificate-identity-regexp="^https://github.com/whiteprints/whiteprints/.github/workflows/upload_artifacts.yml?" \
    --bundle <path_to_the_release_artifact>.sigstore.json \
    <path_to_the_release_artifact>
```

Where:

  - `<path_to_the_artifact>` is the path to the artifact you want to verify.
  - `<path_to_the_release_artifact>.sigstore.json` is the path to the sigstore
    bundle associated with the artifact.

The sigstore bundles are available to download in the GitHub action summary
that produced them.

For more details on [cosign] and [sigstore], refer to their official
documentation.

[build attestation]: https://docs.github.com/en/actions/security-for-github-actions/using-artifact-attestations/using-artifact-attestations-to-establish-provenance-for-builds
[cosign]: https://docs.sigstore.dev/cosign/
[sigstore]: https://www.sigstore.dev/
