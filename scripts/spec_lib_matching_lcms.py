

from processing import *
from similarity_measures import *
import pandas as pd
import argparse
from pathlib import Path
import sys


# create new ArgumentParser object so we can extract command-line input
parser = argparse.ArgumentParser()

# Add optional command-line arguments
parser.add_argument('--query_data', metavar='\b', help='CSV file of query mass spectrum/spectra to be identified. Each row should correspond to a mass spectrum, the left-most column should contain an identifier, and each of the other columns should correspond to a single mass/charge ratio. Mandatory argument.')
parser.add_argument('--reference_data', metavar='\b', help='CSV file of the reference mass spectra. Each row should correspond to a mass spectrum, the left-most column should contain in identifier (i.e. the CAS registry number or the compound name), and the remaining column should correspond to a single mass/charge ratio. Default = LCMS GNPS Library.')
parser.add_argument('--similarity_measure', metavar='\b', help='Similarity measure: options are \'cosine\', \'shannon\', \'renyi\', and \'tsallis\'. Default = cosine.')
parser.add_argument('--spectrum_preprocessing_order', metavar='\b', help='The LCMS spectrum preprocessing transformations and the order in which they are to be applied. Note that these transformations are applied prior to computing similarity scores. Format must be a string with 2-4 characters chosen from W, C, M, L representing weight-factor-transformation, cleaning (i.e. centroiding and noise removal), matching, and low-entropy transformation. For example, if \'WCM\' is passed, then each spectrum will undergo a weight factor transformation, then cleaning, and then matching. Note that if an argument is passed, then \'M\' must be contained in the argument, since matching is a required preprocessing step in spectral library matching of LCMS data. Default: CMWL')
parser.add_argument('--window_size', metavar='\b', help='Window size parameter used in (i) centroiding and (ii) matching a query spectrum and a reference library spectrum. Default = 0.5')
parser.add_argument('--noise_threshold', metavar='\b', help='Ion fragments (i.e. points in a given mass spectrum) with intensity less than max(intensities)*noise_threshold are removed. Default = 0')
parser.add_argument('--wf_mz', metavar='\b', help='Mass/charge weight factor parameter. Default = 0.')
parser.add_argument('--wf_intensity', metavar='\b', help='Intensity weight factor parameter. Default = 1.')
parser.add_argument('--LET_threshold', metavar='\b', help='Low-entropy transformation threshold parameter. Spectra with Shannon entropy less than LET_threshold are transformed according to intensitiesNew=intensitiesOriginal^{(1+S)/(1+LET_threshold)}. Default = 0.')
parser.add_argument('--entropy_dimension', metavar='\b', help='Entropy dimension parameter. Must have positive value other than 1. When the entropy dimension is 1, then Renyi and Tsallis entropy are equivalent to Shannon entropy. Therefore, this parameter only applies to the renyi and tsallis similarity measures. This parameter will be ignored if similarity measure cosine or shannon is chosen. Default = 1.1.')
parser.add_argument('--normalization_method', metavar='\b', help='Method used to normalize the intensities of each spectrum so that the intensities sum to 1. Since the objects entropy quantifies the uncertainy of must be probability distributions, the intensities of a given spectrum must sum to 1 prior to computing the entropy of the given spectrum intensities. Options: \'standard\' and \'softmax\'. Default = standard.')
parser.add_argument('--n_top_matches_to_save', metavar='\b', help='The number of top matches to report. For example, if n_top_matches_to_save=5, then for each query spectrum, the five reference spectra with the largest similarity with the given query spectrum will be reported. Default = 1.')
parser.add_argument('--output_identification', metavar='\b', help='Output CSV file containing the most-similar reference spectra for each query spectrum along with the corresponding similarity scores. Default is to save identification output in current working directory (i.e. same directory this script is contained in) with filename \'output_lcms_identification.csv\'.')
parser.add_argument('--output_similarity_scores', metavar='\b', help='Output CSV file containing similarity scores between all query spectrum/spectra and all reference spectra. Each row corresponds to a query spectrum, the left-most column contains the query spectrum/spectra identifier, and the remaining column contain the similarity scores with respect to all reference library spectra. If no argument passed, then this CSV file is written to the current working directory with filename \'output_lcms_all_similarity_scores\'.csv.')

# parse the user-input arguments
args = parser.parse_args()



# import the query library
if args.query_data is not None:
    df_query = pd.read_csv(args.query_data)
else:
    df_query = pd.read_csv(f'{Path.cwd()}/../data/lcms_query_library_tmp.csv')
    print('No argument passed to query_data; using default LCMS library')



# get the spectrum preprocessing order
print('Performing spectral library matching on LCMS data\n')
if args.spectrum_preprocessing_order is not None:
    spectrum_preprocessing_order = list(args.spectrum_preprocessing_order)
else:
    spectrum_preprocessing_order = ['C', 'M', 'W', 'L']


# load the reference library
if args.reference_data is not None:
    df_reference = pd.read_csv(args.reference_data)
else:
    print('Using default LCMS reference library (from GNPS)\n')
    df_reference = pd.read_csv(f'{Path.cwd()}/../data/lcms_reference_library.csv')


# load the weight factor parameters
if args.wf_mz is not None:
    wf_mz = float(args.wf_mz)
else:
    wf_mz = 0

if args.wf_intensity is not None:
    wf_intensity = float(args.wf_intensity)
else:
    wf_intensity = 1


# load the entropy dimension parameter (if applicable)
if args.similarity_measure == 'renyi' or args.similarity_measure == 'tsallis':
    if args.entropy_dimension is not None:
        q = float(args.entropy_dimension)
    else:
        q = 1.1


# load the window size parameter
if args.window_size is not None:
    window_size = float(args.window_size)
else:
    window_size = 0.5


# load the noise removal parameter
if args.noise_threshold is not None:
    noise_threshold = float(args.noise_threshold)
else:
    noise_threshold = 0


# load the low-entropy transformation threshold
if args.LET_threshold is not None: 
    LET_threshold = float(args.LET_threshold)
else:
    LET_threshold = 0


# set the normalization method
if args.normalization_method is not None:
    normalization_method = args.normalization_method
else:
    normalization_method = 'standard'


# specify the similarity measure to use
if args.similarity_measure is not None:
    similarity_measure = args.similarity_measure
else:
    similarity_measure = 'cosine'


# get the number of most-similar reference library spectra to report for each query spectrum
if args.n_top_matches_to_save is not None:
    n_top_matches_to_save = int(args.n_top_matches_to_save)
else:
    n_top_matches_to_save = 1



# comment/remove this line before sharing code!
#df_reference = df_reference.iloc[0:5000,:]


# get unique query/reference library IDs; each query/reference ID corresponds to exactly one query/reference mass spectrum
unique_query_ids = df_query.iloc[:,0].unique()
unique_reference_ids = df_reference.iloc[:,0].unique()
print(len(unique_query_ids))
print(len(unique_reference_ids))

# compute the similarity score between each query library spectrum/spectra and all reference library spectra
all_similarity_scores =  []
for query_idx in range(0,len(unique_query_ids)):
    #print(query_idx)
    q_idxs_tmp = np.where(df_query.iloc[:,0] == unique_query_ids[query_idx])[0]
    q_spec_tmp = np.asarray(pd.concat([df_query.iloc[q_idxs_tmp,1], df_query.iloc[q_idxs_tmp,2]], axis=1).reset_index(drop=True))
    q_spec = q_spec_tmp

    # compute the similarity score between the given query spectrum and all spectra in the reference library
    similarity_scores = []
    for ref_idx in range(0,len(unique_reference_ids)):
        #print(ref_idx)
        if ref_idx % 100 == 0:
            print(f'Query spectrum #{query_idx} has had its similarity with {ref_idx} reference library spectra computed')
        r_idxs_tmp = np.where(df_reference.iloc[:,0] == unique_reference_ids[ref_idx])[0]
        r_spec = np.asarray(pd.concat([df_reference.iloc[r_idxs_tmp,1], df_reference.iloc[r_idxs_tmp,2]], axis=1).reset_index(drop=True))

        for transformation in spectrum_preprocessing_order:
            if transformation == 'C':
                q_spec = clean_spectrum(q_spec, noise_removal=noise_threshold, window_size=window_size) 
                r_spec = clean_spectrum(r_spec, noise_removal=noise_threshold, window_size=window_size) 
            if transformation == 'M':
                m_spec = match_peaks_in_spectra(spec_a=q_spec, spec_b=r_spec, window_size=window_size)
                q_spec = m_spec[:,0:2]
                r_spec = m_spec[:,[0,2]]
            if transformation == 'W':
                q_spec[:,1] = np.power(q_spec[:,0], wf_mz) * np.power(q_spec[:,1], wf_intensity)
                r_spec[:,1] = np.power(r_spec[:,0], wf_mz) * np.power(r_spec[:,1], wf_intensity)
            if transformation == 'L':
                q_spec[:,1] = transform_int(q_spec[:,1], LET_threshold, normalization_method=normalization_method)
                r_spec[:,1] = transform_int(r_spec[:,1], LET_threshold, normalization_method=normalization_method)

        q_ints = q_spec[:,1]
        r_ints = r_spec[:,1]

        if similarity_measure == 'cosine':
            similarity_score = S_cos(q_ints, r_ints)
        else:
            q_ints = normalize(q_ints, method = normalization_method)
            r_ints = normalize(r_ints, method = normalization_method)

            if similarity_measure == 'shannon':
                similarity_score = S_shannon(q_ints, r_ints)
            elif similarity_measure == 'renyi':
                similarity_score = S_renyi(q_ints, r_ints, q)
            elif similarity_measure == 'tsallis':
                similarity_score = S_tsallis(q_ints, r_ints, q)

        similarity_scores.append(similarity_score)
    all_similarity_scores.append(similarity_scores)


df_scores = pd.DataFrame(all_similarity_scores, columns = unique_reference_ids)
df_scores.index = unique_query_ids
df_scores.index.names = ['Query Spectrum ID']


out = []
scores = []
for i in range(0,df_scores.shape[0]):
    top_ref_specs_tmp = df_scores.iloc[i,:].nlargest(n_top_matches_to_save,keep='all')
    pred = ';'.join(map(str,top_ref_specs_tmp.index.to_list()))
    score = top_ref_specs_tmp.values[0]
    out.append([pred,score])
    scores.append(score)


cnames_preds = []
cnames_scores = []
for i in range(0,int(len(out[0])/2)):
    cnames_preds.append(f'N{i+1}.PRED')
    cnames_scores.append(f'N{i+1}.SIMILARITY.SCORE')

df_top_ref_specs = pd.DataFrame(out, columns = [*cnames_preds, *cnames_scores])
df_top_ref_specs.index = unique_query_ids
df_top_ref_specs.index.names = ['Query Spectrum ID']

# write spectral library matching results to disk
if args.output_identification is not None:
    df_top_ref_specs.to_csv(args.output_identification)
else:
    df_top_ref_specs.to_csv(f'{Path.cwd()}/output_lcms_identification.csv')


# write all similarity scores to disk
df_scores.columns = ['Reference Spectrum ID: ' + col for col in  list(map(str,df_scores.columns.tolist()))]
if args.output_similarity_scores is not None:
    df_scores.to_csv(args.output_similarity_scores)
else:
    df_scores.to_csv(f'{Path.cwd()}/output_lcms_all_similarity_scores.csv')



