# Domain-knowledge source contracts

Domain knowledge is represented by versioned descriptors, not by embedding retrieved content into policy files.

Schema:

`agora-ai-sdlc/domain-knowledge-source/v1`

Supported source kinds are:

- `repository-docs`
- `wiki`
- `files`
- `api`
- `vector-store`

## Descriptor fields

A source declares:

- provider-neutral id;
- owner;
- classification;
- revision;
- scope;
- logical/opaque reference;
- description;
- string metadata.

The descriptor contains references only. It does not contain document bodies, embeddings, credentials, request headers, or provider endpoints.

## Reference boundary

Raw `http://` and `https://` endpoints are intentionally rejected by the v1 descriptor. External systems are referenced through logical source identifiers such as:

`knowledge:wiki/enterprise-architecture`

or:

`knowledge:api/architecture-catalog`

A runtime/integration adapter may resolve that logical reference later under separate credentials and data-handling policy. The descriptor itself stays portable.

## Secret and endpoint policy

The parser rejects fields named like credentials or connection details, including token, password, secret, api_key, authorization, headers, endpoint, and url. Credential-like query material in references is also rejected without echoing the sensitive value.

This contract does not fetch content and performs no network access.
