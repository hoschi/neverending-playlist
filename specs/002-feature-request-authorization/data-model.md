# Data Model: Authorization

## Entities

### UserAuthorization
Represents the authorization granted by a user to the application. This is not a database model but a conceptual representation of the data the application will handle.

- **spotify_user_id** (string): The unique identifier for the Spotify user.
- **access_token** (string): The short-lived token to make API requests.
- **refresh_token** (string): The long-lived token used to obtain a new access token.
- **expires_at** (integer): The timestamp when the access token expires.
- **scope** (string): The scopes of access granted by the user.

## Relationships
- A `UserAuthorization` is associated with a single Spotify user. For the scope of this application, we will only manage one such authorization at a time, representing the application's own authorization to act on behalf of the user who grants permission.
