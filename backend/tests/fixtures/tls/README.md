These certificates and the **public, test-only** server private key are local
loopback fixtures. They must never be used outside tests or installed into an
OS/browser certificate store. The test CA private key is not included.

`valid.crt` covers localhost/127.0.0.1 through 2040; `expired.crt` expired in
2021; `wrong-host.crt` covers wronghost.invalid. All three use server.key.
Tests load root.crt only into their own ephemeral SSL contexts.
