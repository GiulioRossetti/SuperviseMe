# Social Login Setup

SuperviseMe supports OAuth2 login with Google and ORCID. This allows users to sign in using their existing accounts from these providers.

## Google Login Setup

To enable Google login, you need to create a project in the Google Cloud Console and obtain OAuth credentials.

1.  **Create a Project**:
    - Go to the [Google Cloud Console](https://console.cloud.google.com/).
    - Create a new project or select an existing one.

2.  **Configure OAuth Consent Screen**:
    - Navigate to **APIs & Services** > **OAuth consent screen**.
    - Choose **External** user type (unless you are in a Google Workspace organization).
    - Fill in the required fields (App name, User support email, Developer contact information).
    - Add scopes: `openid`, `email`, `profile`.
    - Save and continue.

3.  **Create Credentials**:
    - Navigate to **APIs & Services** > **Credentials**.
    - Click **Create Credentials** > **OAuth client ID**.
    - Application type: **Web application**.
    - Name: `SuperviseMe` (or your preferred name).
    - **Authorized JavaScript origins**: Add your application's base URL (e.g., `https://your-domain.com`).
    - **Authorized redirect URIs**: Add the callback URL: `https://your-domain.com/login/google/callback`.
        - *Note: For local development, use `http://localhost:8080/login/google/callback`.*
    - Click **Create**.

4.  **Configure Environment Variables**:
    - Copy the **Client ID** and **Client Secret**.
    - Add them to your `.env` file:
      ```env
      GOOGLE_CLIENT_ID=your-client-id
      GOOGLE_CLIENT_SECRET=your-client-secret
      ```

## ORCID Login Setup

To enable ORCID login, you need to register a public API client with ORCID.

1.  **Register for an ORCID Account**:
    - If you don't have one, register at [ORCID](https://orcid.org/register).

2.  **Register a Public API Client**:
    - Go to [Developer Tools](https://orcid.org/developer-tools).
    - Under **Public API**, click **Register a Public API client**.
    - Fill in the details:
        - **Name**: SuperviseMe
        - **Website URL**: Your application's URL (e.g., `https://your-domain.com`).
        - **Description**: Thesis supervision platform.
        - **Redirect URIs**: Add the callback URL: `https://your-domain.com/login/orcid/callback`.
            - *Note: For local development, use `http://localhost:8080/login/orcid/callback`.*
    - Save the configuration.

3.  **Configure Environment Variables**:
    - Copy the **Client ID** and **Client Secret**.
    - Add them to your `.env` file:
      ```env
      ORCID_CLIENT_ID=your-client-id
      ORCID_CLIENT_SECRET=your-client-secret
      ```

## Testing Social Login

1.  Restart your application to load the new environment variables.
2.  Go to the login page (`/login`).
3.  You should see "Sign in with Google" and "Sign in with ORCID" buttons (if configured).
4.  Click on a button to initiate the OAuth flow.
5.  After successful authentication, a new user account will be created (pending admin approval) or you will be logged in if the account already exists.

## Notes

-   **HTTPS Requirement**: OAuth providers generally require HTTPS for redirect URIs (except for localhost). Ensure your production deployment uses HTTPS.
-   **User Approval**: New accounts created via social login are disabled by default. An administrator must approve them in the Admin Dashboard.
