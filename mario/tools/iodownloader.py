from pymrio.tools.iodownloader import (download_eora26,
                                       download_exiobase1,
                                       download_exiobase2,
                                       download_exiobase3,
                                       download_oecd,
                                       download_wiod2013,
)

import os
import requests
import shutil



def download_hybrid_exiobase(path):

    exiobase_files = {
        "MR_HUSE_2011_v3_3_18.csv":"https://zenodo.org/record/7244919/files/MR_HUSE_2011_v3_3_18.csv?download=1",
        "MR_HSUTs_2011_v3_3_18_FD.csv":"https://zenodo.org/record/7244919/files/MR_HSUTs_2011_v3_3_18_FD.csv?download=1",
        "MR_HSUP_2011_v3_3_18.csv":"https://zenodo.org/record/7244919/files/MR_HSUP_2011_v3_3_18.csv?download=1",
        "MR_HSUTs_2011_v3_3_18_extensions.xlsx":"https://zenodo.org/record/7244919/files/MR_HSUTs_2011_v3_3_18_extensions.xlsx?download=1",
        "metadata.xlsx": "https://zenodo.org/record/7244919/files/Classifications_v_3_3_18.xlsx?download=1",
    }

    if os.path.exists(path):
        shutil.rmtree(path)
    
    os.mkdir(path)


    for file,url in exiobase_files.items():
        file_path = f"{path}/{file}"

        response = requests.get(url)

        open(file_path, "wb").write(response.content)