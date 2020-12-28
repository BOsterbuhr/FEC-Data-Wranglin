import pandas as pd
import fnmatch

# Imports for ngrams()
import re
from ftfy import fix_text

# Imports for awesome_cossim_top()
import numpy as np
from scipy.sparse import csr_matrix, isspmatrix_csr
import sparse_dot_topn.sparse_dot_topn as ct

# Import for vectorize
from sklearn.feature_extraction.text import TfidfVectorizer

def _csv_to_df(path: str):
    df = pd.read_csv(f"data/raw_data/{path}", index_col=0)
    df.fillna(value="", inplace=True)
    return df
    
        

def _get_df_columns(df):
    column_list = df.columns.values.tolist()
    return column_list


class DataCleaner:
    """
    Instantiated with a dataframe its column names, and size of lowest_similarity and ngram_size. 
    DataCleaner methods to provide a smart deduplication of column values in a dataframe. 
        i.e. "Not Employeed" is replaced by "Not Employed" or "Apple INC" is replaced with "Apple"
    Utilizes a form of Term Frequency, Inverse Document Frequency to determine similarity between values.


    Parameters:
        path: Pandas.DataFrame.
            Use _csv_to_df to provide df from csv.
        
        lowest_similarity: float
            Lowest similarity percentage of column values to combine.
                i.e. 0.9 = words with 90% or more similarity are combined.

        column_name: str
            A column name from path. Use _get_df_columns to get a list of columns.

        ngram_size: int
            Size of string chunks used to assess similarity between two values.
            3 is normally best but values between 2 and 5 can work.

    Returns:
        A Pandas DataFrame with similar values of column_name combined.

    """

    def __init__(self, path: pd.DataFrame, lowest_similarity: float, column_name: str, ngram_size: int):
        self.df = path
        self.lowest_similarity = lowest_similarity
        self.column_name = column_name
        self.ngram_size = ngram_size
        

    def _ngrams(self, string):
        """
        Takes input `string`, removes non-alphabetic and non-ascii chars and returns a list of slices of input `string`.

        Parameters:
            String: A string to be chunked into size of self.ngram_size.

        Returns:
            A list of strings. 
                i.e. testing with self.ngram_size of 3
                    [' Te', 'Tes', 'est', 'sti', 'tin', 'ing', 'ng ']
        """
        string = str(string)
        string = fix_text(string) # fix text
        string = string.encode("ascii", errors="ignore").decode() #remove non ascii chars
        string = string.lower()
        chars_to_remove = [")","(",".","|","[","]","{","}","'"]
        rx = '[' + re.escape(''.join(chars_to_remove)) + ']'
        string = re.sub(rx, '', string)
        string = string.replace('&', 'and')
        string = string.replace(',', ' ')
        string = string.replace('-', ' ')
        string = string.title() # normalise case - capital at start of each word
        string = re.sub(' +',' ',string).strip() # get rid of multiple spaces and replace with a single
        string = ' '+ string +' ' # pad names for ngrams...
        string = re.sub(r'[,-./]|\sBD',r'', string)
        ngrams = zip(*[string[i:] for i in range(self.ngram_size)])
        return [''.join(ngram) for ngram in ngrams]


    def _awesome_cossim_top(self, A, B, ntop):
        """
        True magic, an improvment on scikit-learn's cosine_similarity function.
        Thanks to ING BANK.

        ING definition:
            This function will return a matrix C in CSR format, where
            C = [sorted top n results and results > lower_bound for each row of A * B]
                Input:
                    A and B: two CSR matrix
                    ntop: n top results
                    self.lowest_similarity: a threshold that the element of A*B must greater than
                Output:
                    C: result matrix
            N.B. if A and B are not CSR format, they will be converted to CSR

        """
        if not isspmatrix_csr(A):
            A = A.tocsr()

        if not isspmatrix_csr(B):
            B = B.tocsr()

        M, K1 = A.shape
        K2, N = B.shape

        if K1 != K2:
            err_str = 'A matrix multiplication will be operated. A.shape[1] must be equal to B.shape[0]!'
            raise ValueError(err_str)
 
        idx_dtype = np.int32
 
        nnz_max = M*ntop

        # basic check. if A or B are all zeros matrix, return all zero matrix directly
        if len(A.indices) == 0 or len(B.indices) == 0:
            indptr = np.zeros(M + 1, dtype=idx_dtype)
            indices = np.zeros(nnz_max, dtype=idx_dtype)
            data = np.zeros(nnz_max, dtype=A.dtype)
            return csr_matrix((data, indices, indptr), shape=(M, N))

        # filled matrices from here on
        indptr = np.zeros(M+1, dtype=idx_dtype)
        indices = np.zeros(nnz_max, dtype=idx_dtype)
        data = np.zeros(nnz_max, dtype=A.dtype)

        ct.sparse_dot_topn(
            M, N, np.asarray(A.indptr, dtype=idx_dtype),
            np.asarray(A.indices, dtype=idx_dtype),
            A.data,
            np.asarray(B.indptr, dtype=idx_dtype),
            np.asarray(B.indices, dtype=idx_dtype),
            B.data,
            ntop,
            self.lowest_similarity,
            indptr, indices, data)

        return csr_matrix((data,indices,indptr),shape=(M,N))


    def _get_matches_df(self, sparse_matrix, name_vector):
        """
        Uses sparse_matrix from _awesome_cossim_top and vector of unique column values from df.
        
        Outputs a Pandas DataFrame of matches and their similarity percentage as a float.
        """
        non_zeros = sparse_matrix.nonzero()
    
        sparserows = non_zeros[0]
        sparsecols = non_zeros[1]
    
        nr_matches = sparsecols.size
    
        left_side = np.empty([nr_matches], dtype=object)
        right_side = np.empty([nr_matches], dtype=object)
        similarity = np.zeros(nr_matches)

        for index in range(0, nr_matches):
            left_side[index] = name_vector[sparserows[index]]
            right_side[index] = name_vector[sparsecols[index]]
            similarity[index] = sparse_matrix.data[index]

        return pd.DataFrame({
                        'left_side': left_side,
                        'right_side': right_side,
                        'similarity': similarity
                        })


    def _replace_matches_df(self):
        """
        Replaces matches using all the other DataCleaner methods.
        Using unique column values, TfidVectorizer uses _ngrams to produce a Tf-idf-weighted document-term matrix.
        _awesome_cossim_top then finds the similarity between column values, returning a df, then all exact matches are removed.
        Finally replacing the original values of the df.
        """
        unique_names = self.df[self.column_name].unique()
        #print(len(unique_names))  # Uncomment to compare how many values have been combined
        vectorizer = TfidfVectorizer(min_df=1, analyzer=self._ngrams)
        tf_idf_matrix = vectorizer.fit_transform(unique_names)
        matches = self._awesome_cossim_top(tf_idf_matrix, tf_idf_matrix.transpose(), 100)
        matches_df = self._get_matches_df(matches, unique_names)
        matches_df = matches_df[matches_df['similarity'] < 0.99999] # Remove all exact matches
        # Future improvement: Use the highest value count of either left or right side to determine which to use as final value.
        for left_side, right_side in zip(matches_df['left_side'], matches_df['right_side']):
            left_count = len(self.df.loc[self.df[self.column_name] == left_side])
            right_count = len(self.df.loc[self.df[self.column_name] == right_side])
            for position, column in zip(self.df.index, self.df[self.column_name]):
                if column == right_side and right_count > left_count:
                    self.df.at[position, self.column_name] = right_side
                elif column == right_side:
                    self.df.at[position, self.column_name] = left_side
                if column == left_side and left_count > right_count:
                    self.df.at[position, self.column_name] = left_side
                elif column == left_side:
                    self.df.at[position, self.column_name] = right_side
                    
        #print(len(self.df[self.column_name].unique())) # Uncomment to compare how many values have been combined
        return self.df


def clean_data(path: str, lowest_similarity: float, ngram_size: int):
    """
    Takes a csv file and combines similar values using ngram_size to determine string chunk sizing.
    

    Parameters:
        path: str
            Path to the CSV file to be cleaned
        lowest_similarity: float
            Lowest similarity percentage of column values to combine.
                i.e. 0.9 = words with 90% or more similarity are combined.
        ngram_size: int
            Size of string chunks used to assess similarity between two values.
            3 is normally best but values between 2 and 5 can work.

    Returns:
        A csv file with all columns' values with similarity at or above lowest_similarity combined.

    """
    df = _csv_to_df(path)
    column_list = _get_df_columns(df)
    count = 0
    name_list = []
    skip_list = ["contribution_receipt_amount", "contributor_street_address", "contributor_state", "contributor_zip", "party"]
    for i in range(len(column_list)+1):
        name_list.append(f"cleaner{str(i)}")   
    replace = DataCleaner._replace_matches_df
    for column in column_list:
        if column in skip_list:
            continue
        print(f"Cleaning {column} column of {path}")
        if count < 1:
            name_list[count] = DataCleaner(df, lowest_similarity, column, ngram_size)
            count += 1
            name_list[count-1]
        
        name_list[count] = DataCleaner(replace(name_list[count-1]), lowest_similarity, column, ngram_size)
        count += 1
        name_list[count-1]
    write_df_as_csv(replace(name_list[count-1]), f"cleaned_{lowest_similarity}_{path}")

def write_df_as_csv(df, filename: str):
    df.to_csv(f"data/cleaned_data/{filename}")

