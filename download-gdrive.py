import requests
import re
import sys
import os

def download_file_from_google_drive(id, destination_arg):
    """
    Downloads a file from Google Drive using its file ID.
    Handles the 'virus scan warning' for large files.
    """
    URL = "https://drive.google.com/uc?export=download"

    session = requests.Session()

    # First request to get the download page or direct download
    response = session.get(URL, params = { 'id' : id }, stream = True)

    # Check if a confirmation token is needed (for large files)
    token = get_confirm_token(response)

    if token:
        # If token found, make a second request with the confirmation
        params = { 'id' : id, 'confirm' : token }
        response = session.get(URL, params = params, stream = True)

    save_response_content(response, destination_arg)

def get_confirm_token(response):
    """
    Extracts the confirmation token from Google Drive's download warning page.
    """
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None

def save_response_content(response, destination_arg):
    """
    Saves the content of the HTTP response to the specified destination.
    Attempts to infer the filename from the response headers if not explicitly given.
    """
    CHUNK_SIZE = 32768 # 32 KB chunks for efficient download

    # Try to extract filename from Content-Disposition header
    filename_from_header = None
    if 'Content-Disposition' in response.headers:
        fname_match = re.findall(r'filename\*?=(?:UTF-8\'\')?\"?([^\"]+)\"?', response.headers['Content-Disposition'])
        if fname_match:
            filename_from_header = requests.utils.unquote(fname_match[0])
            # Sanitize filename for common OS compatibility (remove invalid characters)
            filename_from_header = re.sub(r'[<>:"/\\|?*]', '_', filename_from_header)

    # Determine the final path for saving the file
    final_path = ""

    if os.path.isdir(destination_arg):
        # If destination_arg is an existing directory, append the filename
        if filename_from_header:
            final_path = os.path.join(destination_arg, filename_from_header)
        else:
            # Fallback if no filename could be extracted and destination is a directory
            print(f"Warning: Could not determine original filename from Google Drive. Saving to '{os.path.join(destination_arg, 'downloaded_file')}'")
            final_path = os.path.join(destination_arg, "downloaded_file")
    elif not os.path.dirname(destination_arg) and not os.path.exists(destination_arg):
        # If destination_arg is just a filename (no path), assume current directory
        # If filename_from_header exists, use that, otherwise use the provided arg as the filename
        if filename_from_header:
            final_path = os.path.join(os.getcwd(), filename_from_header)
        else:
            final_path = os.path.join(os.getcwd(), destination_arg) # Use provided arg as filename
            print(f"Warning: No filename in Content-Disposition header, and destination was not a directory. Saving to '{final_path}'")
    else:
        # If destination_arg is a full path including a filename
        # Ensure its parent directory exists
        if os.path.dirname(destination_arg):
            os.makedirs(os.path.dirname(destination_arg), exist_ok=True)
        final_path = destination_arg
        if not filename_from_header:
             print(f"Warning: No filename in Content-Disposition header. Saving to '{final_path}' as specified.")

    # Check if the response status is OK (200) before writing
    if response.status_code == 200:
        try:
            with open(final_path, "wb") as f:
                for chunk in response.iter_content(CHUNK_SIZE):
                    if chunk: # filter out keep-alive new chunks
                        f.write(chunk)
            print(f"File downloaded successfully to: {final_path}")
        except IOError as e:
            print(f"Error writing file to {final_path}: {e}")
            print("Please ensure the destination path is valid and you have write permissions.")
    else:
        print(f"Error downloading file. Status code: {response.status_code}")
        print(f"Response: {response.text}")

def extract_file_id(google_drive_link):
    """
    Extracts the Google Drive file ID from various shareable link formats.
    """
    # Common patterns:
    # https://drive.google.com/file/d/FILE_ID/view?usp=sharing
    # https://drive.google.com/uc?id=FILE_ID
    match = re.search(r'id=([a-zA-Z0-9_-]+)|file/d/([a-zA-Z0-9_-]+)', google_drive_link)
    if match:
        # group(1) for 'id=' pattern, group(2) for 'file/d/' pattern
        return match.group(1) or match.group(2)
    return None

if __name__ == "__main__":
    # Check for correct number of arguments
    if len(sys.argv) < 2:
        print("Usage: python download_gdrive.py <google_drive_link> [destination_path_or_filename]")
        print("  <google_drive_link>: The shareable link from Google Drive (e.g., 'https://drive.google.com/file/d/YOUR_FILE_ID/view?usp=sharing')")
        print("  [destination_path_or_filename]: Optional. The path to save the file. Can be:")
        print("                                  - An existing directory (e.g., '~/Downloads/'). File will use original Google Drive filename.")
        print("                                  - A full file path (e.g., '/tmp/my_iso.iso').")
        print("                                  - A filename (e.g., 'my_iso.iso'). File will be saved in current directory.")
        print("                                  If omitted, the file will be saved in the current directory with its original Google Drive filename.")
        sys.exit(1)

    google_drive_link = sys.argv[1]
    # Default destination to current working directory if not provided
    destination_arg = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    # Extract the file ID from the provided link
    file_id = extract_file_id(google_drive_link)

    if not file_id:
        print("Error: Could not extract file ID from the provided Google Drive link.")
        sys.exit(1)

    print(f"Attempting to download file with ID: {file_id}")
    download_file_from_google_drive(file_id, destination_arg)
