import pandas as pd
import os
import sys
import yaml
import glob
import time

import multiprocessing as mp
sys.path.append('./..')
sys.path.append('./../..')
sys.path.append('./../../..')

try:
    from src.IntegratedOutput.preprocess.country_iso_fetcher import ISO_CODE_OBJ
except:
    from .country_iso_fetcher import ISO_CODE_OBJ


'''
Perform  LEB based checks
LEB data 2 columns : hscode_6, CountryOfOrigin 
'''


def write_df_WD(CONFIG, DIR, f_name, df):
    working_dir = os.path.join(CONFIG['Working_Dir'],DIR)

    f_path = os.path.join(working_dir, f_name)
    df.to_csv(f_path, index=None)


def read_df_WD(CONFIG, DIR, f_name):
    working_dir = os.path.join(CONFIG['Working_Dir'],DIR)
    f_path = os.path.join(working_dir, f_name)
    df = pd.read_csv(f_path, index_col=None, low_memory=False)
    return df


def LEB_check_aux(row, LEB_df, target_col):
    hscode_col = 'hscode_6'

    hsc = row[hscode_col]

    if hsc not in list(LEB_df[hscode_col]):
        return 0
    else:
        try:
            idx = LEB_df.loc[LEB_df[hscode_col] == hsc].index.tolist()[0]
            _list_countries = (LEB_df.at[idx, 'CountryOfOrigin']).split(';')
            if row[target_col] in _list_countries:
                return 1
        except:
            return 0
    return 0


def LEB_file_proc(file_path, CONFIG, DIR, LEB_df):
    df = pd.read_csv(
        file_path,
        low_memory=False,
        usecols=CONFIG[DIR]['LEB_columns'],
        index_col=None
    )
    print(len(df))
    
    target_col = CONFIG[DIR]['CountryOfOrigin']

    if target_col is False:
        print( 'NO LEB')    
        df['LEB_flag'] = 0

    else:
         # Convert to iso code
        target_col = CONFIG[DIR]['CountryOfOrigin']
        df[target_col] = df[target_col].apply(ISO_CODE_OBJ.get_iso_code)
        df['LEB_flag'] = 0
        df['hscode_6'] = df['hscode_6'].astype(str)
        df['LEB_flag'] = df.apply(LEB_check_aux, axis=1, args=(LEB_df, target_col))
        del df[target_col]
    # ======
    # Write df to processing temp location
    # ======
    f_name = 'tmp_' + file_path.split('_')[-1]


    write_df_WD(CONFIG, DIR, f_name, df)
    return True


def get_LEB_match_records(CONFIG, DIR):

    LEB_df = pd.read_csv(CONFIG['LEB_DATA_FILE'], low_memory=False, index_col=None)
    LEB_df['hscode_6'] = LEB_df['hscode_6'].astype(str)

    # ============
    # These are the segmented files , with actual data though cleaned through initial processing
    # ============
    file_list = sorted(glob.glob(
        os.path.join(
            CONFIG['Data_RealSegmented_LOC'], DIR, '**', 'data_test_**.csv')
    ))


    num_proc = 10
    pool = mp.Pool(processes=num_proc)
    print(pool)

    results = [
        pool.apply_async(
            LEB_file_proc,
            args=(file_path, CONFIG, DIR, LEB_df,)
        ) for file_path in file_list
    ]
    output = [p.get() for p in results]
    print (output)

    return None

# ===========================
#  CITES check
# ===========================
def HSCode_check_aux(row, hscode_list):
    hscode_col = 'hscode_6'
    hsc = row[hscode_col]
    if hsc  in hscode_list:
        return 1
    else:
        return 0


def FLAG_file_proc(file_path, CONFIG, DIR, hscode_list, flag_column):

    df = pd.read_csv(
        file_path,
        low_memory=False,
        index_col=None
    )

    df[flag_column] = 0
    df['hscode_6'] = df['hscode_6'].astype(str)
    df[flag_column] = df.apply(HSCode_check_aux, axis=1, args=(hscode_list,))

    # ======
    # Write df to processing temp location
    # ======
    f_name = 'tmp_' + file_path.split('_')[-1]
    write_df_WD(CONFIG, DIR, f_name, df)
    return True


def common_dispatcher(CONFIG, DIR, hscode_list, flag_column):
    # ============
    # The input now is from Working_Dir
    # ============
    file_list = sorted(glob.glob(
        os.path.join(
            CONFIG['Working_Dir'], DIR, '**.csv')
    ))

    num_proc = 10
    pool = mp.Pool(processes=num_proc)

    results = [
        pool.apply_async(
            FLAG_file_proc,
            args=(file_path, CONFIG, DIR, hscode_list,flag_column, )
        ) for file_path in file_list
    ]
    output = [p.get() for p in results]
    print(output)
    return True

# ========
#  Row -wise validator function
# ========
def lacey_check_aux(row, hscode_include_list, hscode_exclude_list):
    row_hscode = row['hscode_6']
    # check 6 digit s

    if row_hscode in hscode_exclude_list: return 0
    if row_hscode in hscode_include_list : return 1

    row_hscode = row_hscode[:4]
    if row_hscode in hscode_include_list : return 1

    return 0

# ========
#  Nested function that handles each file
# ========
def LaceyAct_file_proc(
        file_path,
        CONFIG,
        DIR,
        hscode_include_list,
        hscode_exclude_list,
        flag_column
):
    df = pd.read_csv(
        file_path,
        low_memory=False,
        index_col=None
    )

    df[flag_column] = 0
    df['hscode_6'] = df['hscode_6'].astype(str)
    df[flag_column] = df.apply(
        lacey_check_aux,
        axis=1,
        args=(hscode_include_list, hscode_exclude_list)
    )

    # ======
    # Write df to processing temp location
    # ======
    f_name = 'tmp_' + file_path.split('_')[-1]
    write_df_WD(CONFIG, DIR, f_name, df)
    return True

# -------------- #
#  Function to add in lacey act flag
# -------------- #
def append_lacey_act_flag(
        CONFIG,
        DIR,
        hscode_include_list,
        hscode_exclude_list,
        flag_column
    ):


    # Get all the files from Working directory

    file_list = sorted(glob.glob(
        os.path.join(
            CONFIG['Working_Dir'], DIR, '**.csv')
    ))

    num_proc = 20
    pool = mp.Pool(processes=num_proc)
    results = [
        pool.apply_async(
            LaceyAct_file_proc,
            args=(
                file_path,
                CONFIG,
                DIR,
                hscode_include_list,
                hscode_exclude_list,
                flag_column,
            )
        ) for file_path in file_list
    ]
    output = [p.get() for p in results]
    print(output)
    return True





def get_match_records(CONFIG, DIR):

    sources = [ 'CITES', 'WWF_HighRisk', 'IUCN_RedList']

    for source in sources:
        flag_column = source + '_flag'
        data_file_key = source + '_DATA_FILE'

        source_df = pd.read_csv(
            CONFIG[data_file_key],
            low_memory=False,
            index_col=None,
            header=None
        )

        hscode_list = list(source_df[0])
        t1 = time.time()
        common_dispatcher(CONFIG, DIR, hscode_list, flag_column)
        t2 = time.time()
        print(' Time for ' + source + ' checks ', t2 - t1)

    """
    Add in Lacey Act  Flag 
    """

    source = 'Lacey_Act'
    flag_column = source + '_flag'
    hscode_include_key = '_'.join([source, 'include', 'DATA_FILE'])
    hscode_exclude_key = '_'.join([source, 'exclude', 'DATA_FILE'])

    hscode_include_df = pd.read_csv(
            CONFIG[hscode_include_key],
            low_memory=False,
            index_col=None,
            header=None
        )

    hscode_exclude_df = pd.read_csv(
        CONFIG[hscode_exclude_key],
        low_memory=False,
        index_col=None,
        header=None
    )

    hscode_include = list(hscode_include_df[0].astype(str))
    hscode_exclude = list(hscode_exclude_df[0].astype(str))

    append_lacey_act_flag(
        CONFIG,
        DIR,
        hscode_include,
        hscode_exclude,
        flag_column
    )
    return 0



def main_aux():
    CONFIG_FILE = 'precompute_PanjivaRecordID_hdf.yaml'
    with open(CONFIG_FILE) as f:
        CONFIG = yaml.safe_load(f)

    if not os.path.exists(CONFIG['Working_Dir']):
        os.mkdir(CONFIG['Working_Dir'])
    if not os.path.exists(CONFIG['HDF_OUTPUT_LOC']):
        os.mkdir(CONFIG['HDF_OUTPUT_LOC'])

    process_DIRS = CONFIG['process_dirs']

    for DIR in process_DIRS:

        if not os.path.exists(
                os.path.join(CONFIG['Working_Dir'], DIR)
        ):
            os.mkdir(os.path.join(CONFIG['Working_Dir'], DIR))

        if CONFIG[DIR]['process_LEB']:
            t1 = time.time()
            get_LEB_match_records(CONFIG, DIR)
            t2 = time.time()
            print(' Time for LEB checks ', t2 - t1)

        get_match_records(CONFIG, DIR)

        # =====
        # Combine the files
        # =====
        file_loc = os.path.join(CONFIG['Working_Dir'], DIR)
        file_list = sorted(glob.glob(
            os.path.join(file_loc,'**.csv'))
        )

        master_df = None
        for _file in file_list:
            _tmpdf = pd.read_csv(_file, index_col=None,low_memory=False)
            if master_df is None:
                master_df = _tmpdf
            else:
                master_df = master_df.append(_tmpdf, ignore_index=True)
        op_loc = os.path.join(CONFIG['HDF_OUTPUT_LOC'],DIR)
        if not os.path.exists(op_loc):
            os.mkdir(op_loc)

        f_name = 'HDF_results.csv'
        op_f_path = os.path.join(
            op_loc, f_name
        )
        master_df.to_csv(op_f_path,index=None)
    return

def get_cur_path():
    import inspect
    this_file_path = '/'.join(
        os.path.abspath(
            inspect.stack()[0][1]
        ).split('/')[:-1]
    )

    # os.chdir(this_file_path)
    print(os.getcwd())
    return this_file_path


def main():
    old_path = os.getcwd()
    cur_path =  get_cur_path()
    os.chdir(cur_path)
    main_aux()
    os.chdir(old_path)

main()