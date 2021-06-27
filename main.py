import os.path
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

CATEGORIES = 5

def setup():
    SCOPES = ['https://www.googleapis.com/auth/drive']
    creds = None
    print(json.loads('{"installed":{"client_id":"29648831404-ssoj8mqepnvuac4773pvdqf6kn817rl5.apps.googleusercontent.com","project_id":"newagent-hgfp","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"sUrYnhw8P1F7iKbyQJZkFk3a","redirect_uris":["urn:ietf:wg:oauth:2.0:oob","http://localhost"]}}'))
    flow = InstalledAppFlow.from_client_config(json.loads('{"installed":{"client_id":"29648831404-ssoj8mqepnvuac4773pvdqf6kn817rl5.apps.googleusercontent.com","project_id":"newagent-hgfp","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"sUrYnhw8P1F7iKbyQJZkFk3a","redirect_uris":["urn:ietf:wg:oauth:2.0:oob","http://localhost"]}}'), SCOPES)
    creds = flow.run_local_server(port=0)

    return build('drive', 'v3', credentials=creds)

def get_files(sv, q=None):
    try:
        response = sv.files().list(q=q, fields="files(id, name, mimeType)").execute()
    except:
        return
    files = response.get('files')
    nextPageToken = response.get('nextPageToken')
    while nextPageToken:
        response = sv.files().list(q=q, fields="files(id, name, parents, mimeType)", pageToken=nextPageToken).execute()
        files.extend(response.get('files'))
        nextPagetoken = response.get('nextPageToken')

    docs = []
    for file in files:
        data = sv.files().export(fileId=file['id'], mimeType='text/plain').execute()
        if data:
            docs.append(data.decode('utf-8'))
    print('NUM DOCS:', len(docs))

    return files, docs

def create_file(sv, name="", type="", parent=None):
    file_metadata = {
        'name': name,
        'mimeType': type
    }
    file = sv.files().create(body=file_metadata).execute()
    if parent:
        sv.files().update(
            fileId=file['id'],
            addParents=parent
        ).execute()

    return file

def correct_parent(sv, file, parent):
    if "parents" not in file.keys() or parent not in file['parents']:
        sv.files().update(
            fileId=file['id'],
            addParents=parent
        ).execute()

def setup_folders(sv, folders):
    fds = []

    for folder in folders:
        name = f'folder-{folder+1}'
        # if name not in folders.keys():
        new_folder = create_file(sv, name=name, type="application/vnd.google-apps.folder")
        fds.append(new_folder)

    return fds

def learn(docs):
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(docs)

    true_k = CATEGORIES
    model = KMeans(n_clusters=true_k, init='k-means++', max_iter=100, n_init=1)
    model.fit(X)

    print("Top terms per cluster:")
    order_centroids = model.cluster_centers_.argsort()[:, ::-1]
    terms = vectorizer.get_feature_names()
    for i in range(true_k):
        print("Cluster %d:" % i),
        for ind in order_centroids[i, :10]:
            print(' %s' % terms[ind]),
        print

    print("\n")
    print("Prediction")

    predictions = []
    for doc in docs:
        Y = vectorizer.transform([doc])
        predictions.append(model.predict(Y)[0])
    print(predictions)
    return predictions


def main():
    service = setup()
    files, docs = get_files(service, f"mimeType='application/vnd.google-apps.document'")

    preds = learn(docs)
    folders = setup_folders(service, range(min(preds), max(preds) + 1))

    print(f'{folders = }')

    count = 0
    for file in files:
        fd = folders[preds[count]]
        print(f'{file = }')
        try:
            previous_parents = file.get('parents')[0]
            # Move the file to the new folder
            file = service.files().update(
                fileId=file['id'],
                addParents=fd['id'],
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
        except:
            file = service.files().update(
                fileId=file['id'],
                addParents=fd['id'],
                fields='id, parents'
            ).execute()


        count += 1

main()
