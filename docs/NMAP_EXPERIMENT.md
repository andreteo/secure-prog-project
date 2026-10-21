# Nmap experiment: local service and TLS exposure

This is an optional, narrow addition to the before-and-after presentation. It checks what a client can discover about the two **local** web listeners. It does not test authentication, authorization, SQL injection, CSRF, or the login rate limiter; use the existing HTTP requests and backend tests for those claims.

Nmap was not installed or run when this plan was written. Record actual output only after performing the scan.

## Setup and commands

Install Nmap on the presentation Mac if needed, then check `nmap --version`. From the project root, start the two local versions in one terminal:

```sh
./scripts/start_comparison.sh
```

In another terminal, scan **only this project's loopback ports**:

```sh
nmap -sT -sV -Pn -p 5001,5443 127.0.0.1
```

The expected distinction is HTTP on the baseline port `5001` and HTTPS/TLS on the secured port `5443`. Record what Nmap actually identifies; service detection can be uncertain. To inspect the TLS certificate exposed by the secured listener:

```sh
nmap -sT -Pn -p 5443 --script ssl-cert 127.0.0.1
```

The `ssl-cert` output may show the certificate subject, subject alternative names, and validity dates. It **retrieves** a certificate; it does not prove that a browser trusts it. Keep the existing `curl --cacert local-certs/localhost.crt https://127.0.0.1:5443/api/health` result as the certificate-validation evidence. If Nmap does not recognize the TLS service, report that limitation rather than changing the output.

For the actual secured-only deployment state, stop the comparison and run `./scripts/start.sh --https`; a repeat of the first scan should find no baseline listener on `5001` and the secure listener on `5443`, provided no other process is using those ports. The side-by-side comparison intentionally keeps the insecure server open for demonstration, so its presence in that scan is expected.

## Evidence to capture

Capture one terminal screenshot with the command, Nmap version, target `127.0.0.1`, and the two port results. A second screenshot may show the `ssl-cert` output. Record the date and whether both versions or only the secured version were running. Do not include private keys, passwords, cookies, or CSRF tokens.

Suggested caption: **“Local Nmap service scan of the two demonstration listeners. The baseline uses HTTP on port 5001; the secured presentation uses TLS on port 5443. This identifies transport exposure, not application-level security.”**

## Report-ready interpretation

> A scoped Nmap TCP-connect and service-detection scan was run against `127.0.0.1` on ports 5001 and 5443. The baseline and secured listeners were compared for their exposed transport protocols. An `ssl-cert` check inspected the certificate presented on the secured port, while a separate `curl --cacert` request tested certificate validation. Nmap supported the transport comparison but could not assess ownership checks, password verification, or SQL parameterization; those properties were tested with direct requests and database-state checks. [Replace this sentence with the actual observed port and certificate results.]

Do not claim the local scan establishes public-network exposure or production security. Both Flask servers bind to `127.0.0.1`; this experiment observes them from the same machine.

Nmap references: [Port-scanning techniques](https://nmap.org/book/man-port-scanning-techniques.html), [service and version detection](https://nmap.org/book/man-version-detection.html), and [`ssl-cert` script](https://nmap.org/nsedoc/scripts/ssl-cert.html).
