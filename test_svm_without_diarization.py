import os
import csv
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from pyAudioAnalysis import MidTermFeatures as aF
from pyAudioAnalysis import audioBasicIO
from pyAudioAnalysis import audioTrainTest as aT
from sklearn import svm
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.naive_bayes import GaussianNB, MultinomialNB, BernoulliNB
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis
from sklearn.ensemble import AdaBoostClassifier
from sklearn import metrics
from sklearn.metrics import accuracy_score
import assemblyai as aai
import os
from nltk.tokenize import word_tokenize
from nltk.probability import FreqDist

#from diarization_and_feature_extraction_from_text import text_features

'''aT.extract_features_and_train(["/home/droidis/Desktop/sample/1", "/home/droidis/Desktop/sample/2"], 1.0, 1.0, aT.shortTermWindow, aT.shortTermStep, "knn", "svmSMtemp", False)
#aT.file_classification("data/doremi.wav", "svmSMtemp","svm")'''


def extract_features_to_csv(audios):
    """
    Extract audio features from a folder of WAV files and save them to a CSV file.

    Args:
        folder_path (str): Path to the folder containing audio files.
        csv_output_path (str): Path to save the extracted features as a CSV file.
    """
    # List all WAV files in the folder
    audio_files = [os.path.join(audios, f) for f in os.listdir(audios) if f.endswith('.mp3')]

    # Check if there are valid audio files
    if not audio_files:
        raise ValueError("No mp3 files found in the specified folder.")

    all_features = []  # To store features from all files
    file_names = []  # To store corresponding file names

    for file_path in audio_files:
        # Read audio file
        sampling_rate, signal = audioBasicIO.read_audio_file(file_path)
        if signal is None:
            print(f"Error reading file {file_path}, skipping...")
            continue

        # Ensure mono audio
        signal = audioBasicIO.stereo_to_mono(signal)

        # Extract mid-term features
        mt_features, _, feature_names = aF.mid_feature_extraction(
            signal, sampling_rate, 1.0 * sampling_rate, 0.5 * sampling_rate, 0.05 * sampling_rate, 0.05 * sampling_rate
        )

        # Average features over windows
        avg_features = np.mean(mt_features, axis=1)
        all_features.append(avg_features)
        file_names.append(os.path.basename(file_path))

    # Combine file names and features into a DataFrame
    mfcc = pd.DataFrame(all_features, columns=feature_names)
    mfcc.insert(0, 'File', file_names)  # Insert file names as the first column

    # Write DataFrame to CSV
    mfcc.to_csv("mfcc.csv.csv", index=False)

    print(f"Features saved to mfcc.csv.csv")
    return mfcc

def diarization_and_feature_extraction_from_text(audios):
    text_features = pd.DataFrame(columns=['filename', 'Word Variance', 'Hapax Legomena'])
    # Replace with your API key
    aai.settings.api_key = "262ec24608c0442483768e3004d70d53"
    config = aai.TranscriptionConfig(speaker_labels=True)

    directory = os.fsencode(audios)

    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        if filename.endswith(".mp3"):
            url = audios + '/' + filename
            transcriber = aai.Transcriber()
            transcript = transcriber.transcribe(
                url,
                config=config
            )

            for utterance in transcript.utterances:
                # print(f"Speaker {utterance.speaker}: {utterance.text}")
                text = utterance.text

        tokens = word_tokenize(text.lower())

        # Frequency distribution
        fdist = FreqDist(tokens)
        word_variance = len(fdist) / len(tokens)  # Lexical richnes
        hapax_legomena = len([word for word, freq in fdist.items() if freq == 1])
        text_features = text_features._append(
            {'filename': filename, 'Word Variance': word_variance, 'Hapax Legomena': hapax_legomena}, ignore_index=True)

    text_features = text_features.sort_values('filename')
    text_features.to_csv('text_features.csv', index=False)
    return text_features

def fuse_data(mfcc, text_features, groundtruth):
    # final dataframe preparation
    mfcc = mfcc.sort_values('File')
    mfcc['File'] = mfcc['File'].str.replace('.mp3', '')
    text_features['filename'] = text_features['filename'].str.replace('.mp3', '')
    final_features = mfcc.merge(groundtruth, left_on='File', right_on='adressfname')
    final_features = final_features.merge(text_features, left_on='File', right_on='filename')
    final_features = final_features.drop('adressfname', axis=1)
    final_features = final_features.drop('filename', axis=1)

    # handle missing education values by assigning the mean. Should i assign 2 different means one for each class?
    mean = final_features[['educ']].mean()
    final_features['educ'] = final_features['educ'].replace(np.nan, float(mean))

    final_features = final_features.dropna(axis=0)

    # handle categorical values in gender column
    final_features['gender'] = final_features['gender'].map({'male': 0, 'female': 1})

    final_features.to_csv('final_features.csv', index=False)

    return final_features


def main(audios):
    mfcc = extract_features_to_csv(audios)
    text_features = diarization_and_feature_extraction_from_text(audios)
    training_groundtruth = pd.read_csv('training-groundtruth.csv')

    #final dataframe preparation
    final_features = fuse_data(mfcc,text_features, training_groundtruth)

    X = final_features.drop('dx', axis=1)  # Features
    X = X.drop('File', axis=1)

    y = final_features.dx  # Target variable

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=16)

    model = svm.SVC(kernel='linear')
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    cnf_matrix = metrics.confusion_matrix(y_test, y_pred)
    print(cnf_matrix)
    accuracy = accuracy_score(y_pred, y_test)
    print(accuracy)

    '''mfcc.csv = mfcc.csv.sort_values('File')
    mfcc.csv['File'] = mfcc.csv['File'].str.replace('.mp3', '')
    text_features['filename'] = text_features['filename'].str.replace('.mp3', '')
    final_features = mfcc.csv.merge(training_groundtruth, left_on='File', right_on='adressfname')
    final_features = final_features.merge(text_features, left_on='File', right_on='filename')
    final_features = final_features.drop('adressfname', axis=1)
    final_features = final_features.drop('filename', axis=1)
    mean = final_features[['educ']].mean()
    final_features['educ'] = final_features['educ'].replace(np.nan, float(mean))
    final_features = final_features.dropna(axis=0)
    final_features['gender'] = final_features['gender'].map({'male': 0, 'female': 1})
    final_features.to_csv('final_features.csv', index=False)

    
    return final_features'''

# Example usage
#extract_features_to_csv("/home/droidis/Desktop/train_edited", "/home/droidis/Desktop/MFCC_edited.csv")
#extract_features_to_csv("/home/droidis/Desktop/train_edited", "MFCC_edited.csv")


audios = "train"

#main(audios)

mfcc = pd.read_csv("mfcc.csv")
text_features= pd.read_csv("text_features.csv")
training_groundtruth = pd.read_csv("training-groundtruth.csv")

final_features = fuse_data(mfcc,text_features, training_groundtruth)



X = final_features.drop('dx', axis=1)  # Features
X = X.drop('File', axis=1)
y = final_features.dx  # Target variable

# normalise
scaler = MinMaxScaler()

# Normalize the DataFrame
X = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

# standardize
scaler = StandardScaler()

# Standardize the DataFrame
X = pd.DataFrame(scaler.fit_transform(X), columns=X.columns)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=16)

#model = svm.SVC(kernel='linear')
#model = LogisticRegression()
model = KNeighborsClassifier(n_neighbors=10) # for normalised data it gives 76% accuracy, 92% for non initial and 76% for standardized. Test different amount of neighbours
#model = DecisionTreeClassifier()
#model = RandomForestClassifier(n_estimators=100)
#model = GradientBoostingClassifier(n_estimators=100)
#model = GaussianNB() # 81% for normalized and standardized, 83% for initial data
#model = LinearDiscriminantAnalysis() #73% for initial data, normalized and standardized
#model = QuadraticDiscriminantAnalysis() # 50% for initial, 69% for normalised data, and 80% for standardized
#model = AdaBoostClassifier(n_estimators=50)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
cnf_matrix = metrics.confusion_matrix(y_test, y_pred)
print(cnf_matrix)
accuracy = accuracy_score(y_pred, y_test)
print(accuracy)













#X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=16)



