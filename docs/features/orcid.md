# ORCID Integration

SuperviseMe provides integration with ORCID to allow researchers and supervisors to easily import and display their professional activities.

## Features

- **Authentication**: Log in using your ORCID credentials.
- **Data Synchronization**: Fetch your Works, Employment, Education, and Funding information from ORCID.
- **Visualization**: View your imported activities in organized tabs on your profile.
- **Export**: Export selected activities or your entire list to BibTeX format.

## How to Use

### 1. Connect your Account
To use the ORCID features, you must log in to SuperviseMe using your ORCID account.
- On the Login page, click the **Login with ORCID** button.
- If you don't have an account, one will be created for you based on your ORCID profile.

### 2. Sync Data
Once logged in, go to your **Profile** page.
- You will see an "ORCID Publications" section.
- Click the **Sync from ORCID** button.
- The system will fetch your public data from ORCID:
    - **Works**: Publications, datasets, etc.
    - **Affiliations**: Employment and Education history.
    - **Funding**: Grants and awards.

### 3. View Activities
Your activities are displayed in tabs:
- **Works**: List of your publications.
- **Affiliations**: Your employment and education history.
- **Funding**: Your funding records.

### 4. Export to BibTeX
You can export your activities to a BibTeX file for use in LaTeX or other reference managers.
- **Export All**: Click "Export All" to download a BibTeX file containing all your synchronized activities.
- **Export Selected**: Check the boxes next to specific items you wish to export, then click "Export Selected".

## Technical Details

- **Scope**: The application uses the `/read-public` scope to access your public ORCID record.
- **Storage**: Data is cached locally in the database for quick access and offline viewing. Syncing overwrites the local cache with the latest data from ORCID.
