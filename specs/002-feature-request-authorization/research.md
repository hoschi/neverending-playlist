# Research: Authorization Code Flow

## Decision: Use Spotipy with SpotifyOAuth
- **Rationale**: `spotipy` is the most mature and feature-complete Python library for the Spotify Web API. The `SpotifyOAuth` class directly implements the Authorization Code Flow, handling URL generation, token exchange, and automatic token refreshing. This significantly reduces implementation complexity and aligns with industry best practices.
- **Alternatives considered**:
    - **Manual OAuth Flow**: Building the OAuth flow manually with a library like `requests-oauthlib` would require more boilerplate code, be more error-prone, and necessitate manual management of token storage and refresh logic. Given the existence of a high-level library, this is unnecessary.

## Decision: Store Refresh Token in `.env` file (encrypted)
- **Rationale**: As per the clarification session, the refresh token will be stored in the `.env` file. To enhance security, the application will be responsible for encrypting the token before writing it and decrypting it upon reading. A symmetric encryption key (stored separately, e.g., in another environment variable or a secure vault in production) will be used for this purpose. This approach provides a reasonable level of security for this specific application's needs without introducing the complexity of a full-fledged secrets management system.
- **Alternatives considered**:
    - **Database Storage**: Storing the token in a database would require setting up and managing a database, which adds significant overhead for a single value.
    - **Secrets Manager**: While the most secure option, using a service like AWS Secrets Manager or HashiCorp Vault is overkill for this project's current scale and introduces external dependencies.

## Unresolved Questions
- None. All initial ambiguities have been resolved.
