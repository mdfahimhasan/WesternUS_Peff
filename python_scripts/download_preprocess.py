import os
import ee
import pickle
import zipfile
import requests
import itertools
import numpy as np
import pandas as pd
from glob import glob
from osgeo import gdal
import geopandas as gpd
from system_process import makedirs, copy_file
from raster_process import read_raster_arr_object, write_array_to_raster, mosaic_rasters, clip_resample_reproject_raster

# ee.Authenticate()

# # if ee.Authenticate() doesn't work or gives 'gcloud' error go to the
# 'https://developers.google.com/earth-engine/guides/python_install' link and follow instructions for
# local/remote machine.
# In local machine, install gcloud (if not already installed) and follow the steps from the link to authenticate.
# For remote machine, https://www.youtube.com/watch?v=k-8qFh8EfFA this link was helpful for installing gcloud.
# Couldn't figure out how to authenticate in server pc, will try with new workstation
# If autheticated, no need to run the authentication process again. Just start from ee.initialize()

no_data_value = -9999
model_res = 0.02000000000000000389  # in deg, 2 km
WestUS_raster = '../Data/shapefiles/Western_US/Western_US_refraster_2km.tif'


def download_from_url(download_dir, url_list):
    """
    Download Data from url.

    :param download_dir: File path to save downloaded data.
    :param url_list: A list of url/urls to download.

    :return:
    """
    makedirs([download_dir])
    for url in url_list:
        fname = url.rsplit('/', 1)[1]
        print(f'Downloading {fname}......')
        r = requests.get(url, allow_redirects=True)
        download_fname = os.path.join(download_dir, fname)
        open(download_fname, 'wb').write(r.content)
        print('Download complete')
        return download_fname


def extract_data(zip_dir, out_dir, search_by='*.zip', rename_file=True):
    """
    Extract zipped file.

    :param zip_dir: File path of zipped file.
    :param out_dir: File path where data will be extracted.
    :param search_by: Keyword for searching files, default is '*.zip'.
    :param rename_file: True if file rename is required while extracting.

    :return: List of zipped files (can be used for deleting all the files). This function will unzip these files.
    """
    print('Extracting zip files.....')

    makedirs([out_dir])
    all_zipped_files = glob(os.path.join(zip_dir, search_by))

    for zip_file in all_zipped_files:
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            if rename_file:
                zip_key = zip_file[zip_file.rfind(os.sep) + 1:zip_file.rfind('.')]
                zip_info = zip_ref.infolist()[0]
                zip_info.filename = zip_key + '.tif'
                zip_ref.extract(zip_info, path=out_dir)
            else:
                zip_ref.extractall(path=out_dir)
    return all_zipped_files


def get_gee_dict(data_name):
    ee.Initialize()
    gee_data_dict = {
        'SMAP_SM': 'NASA_USDA/HSL/SMAP10KM_soil_moisture',
        'LANDSAT_NDWI': 'LANDSAT/LC08/C01/T1_8DAY_NDWI',  # check for cloudcover
        'LANDSAT_NDVI': 'LANDSAT/LC08/C01/T1_8DAY_NDVI',  # check for cloudcover
        'GPM_PRECIP': 'NASA/GPM_L3/IMERG_MONTHLY_V06',
        'GRIDMET_PRECIP': 'IDAHO_EPSCOR/GRIDMET',
        'PRISM_PRECIP': 'OREGONSTATE/PRISM/AN81m',
        'VIIRS_NDVI': 'NOAA/VIIRS/001/VNP13A1',  # cloudcover mask added later
        'VIIRS_EVI': 'NOAA/VIIRS/001/VNP13A1',  # cloudcover mask added later
        'VIIRS_EVI2': 'NOAA/VIIRS/001/VNP13A1',  # cloudcover mask added later
        'MODIS_Day_LST': 'MODIS/006/MOD11A2',  # check for cloudcover
        'MODIS_Terra_NDVI': 'MODIS/006/MOD13Q1',  # cloudcover mask added later
        'MODIS_Terra_EVI': 'MODIS/006/MOD13Q1',  # cloudcover mask added later
        'MODIS_NDWI': 'MODIS/006/MOD09A1',  # cloudcover mask added later
        'MODIS_LAI': 'MODIS/006/MCD15A3H',
        'MODIS_ET': 'MODIS/006/MOD16A2',  # unit in kg/m2
        'FAO_ACTUAL_ET': 'FAO/WAPOR/2/L1_AETI_D',
        'FAO_EVAPORATION': 'FAO/WAPOR/2/L1_E_D',
        'FLDAS_BF_GW_RO': 'NASA/FLDAS/NOAH01/C/GL/M/V001',
        'FLDAS_SM': 'NASA/FLDAS/NOAH01/C/GL/M/V001',
        'USDA_CDL': 'USDA/NASS/CDL'  # Recommending not to use this GEE link. Code added separately to download CDL data
    }
    gee_band_dict = {
        'SMAP_SM': 'ssm',
        'LANDSAT_NDWI': 'NDWI', 'NDWI'
                                'LANDSAT_NDVI': 'NDVI',
        'GPM_PRECIP': 'precipitation',
        'GRIDMET_PRECIP': 'pr',
        'PRISM_PRECIP': 'ppt',
        'VIIRS_NDVI': 'NDVI',
        'VIIRS_EVI': 'EVI',
        'VIIRS_EVI2': 'EVI2',
        'MODIS_Day_LST': 'LST_Day_1km',
        'MODIS_Terra_NDVI': 'NDVI',
        'MODIS_Terra_EVI': 'EVI',
        'MODIS_NDWI': ['sur_refl_b02', 'sur_refl_b06'],  # bands for NIR and SWIR, respectively.
        'MODIS_LAI': 'Lai',
        'MODIS_ET': 'ET',
        'FAO_ACTUAL_ET': 'L1_AETI_D',
        'FAO_EVAPORATION': 'L1_E_D',
        'FLDAS_BF_GW_RO': 'Qsb_tavg',
        'FLDAS_SM': 'SoilMoi00_10cm_tavg',
        'USDA_CDL': 'cropland'
    }
    gee_scale_dict = {
        'SMAP_SM': 1,
        'LANDSAT_NDWI': 1,
        'LANDSAT_NDVI': 1,
        'GPM_PRECIP': 1,
        'GRIDMET_PRECIP': 1,
        'PRISM_PRECIP': 1,
        'VIIRS_NDVI': 0.0001,
        'VIIRS_EVI': 0.0001,
        'VIIRS_EVI2': 0.0001,
        'MODIS_Day_LST': 0.02,
        'MODIS_Terra_NDVI': 0.0001,
        'MODIS_Terra_EVI': 0.0001,
        'MODIS_NDWI': 0.0001,
        'MODIS_LAI': 0.1,
        'MODIS_ET': 0.1,
        'FAO_ACTUAL_ET': 0.1,
        'FAO_EVAPORATION': 0.1,
        'FLDAS_BF_GW_RO': 1,
        'FLDAS_SM': 1,
        'USDA_CDL': 1
    }

    aggregation_dict = {
        'SMAP_SM': ee.Reducer.sum(),
        'LANDSAT_NDWI': ee.Reducer.mean(),
        'LANDSAT_NDVI': ee.Reducer.mean(),
        'GPM_PRECIP': ee.Reducer.sum(),
        'GRIDMET_PRECIP': ee.Reducer.sum(),
        'PRISM_PRECIP': ee.Reducer.sum(),
        'VIIRS_NDVI': ee.Reducer.mean(),
        'VIIRS_EVI': ee.Reducer.mean(),
        'VIIRS_EVI2': ee.Reducer.mean(),
        'MODIS_Day_LST': ee.Reducer.mean(),
        'MODIS_Terra_NDVI': ee.Reducer.mean(),
        'MODIS_Terra_EVI': ee.Reducer.mean(),
        'MODIS_NDWI': ee.Reducer.mean(),
        'MODIS_LAI': ee.Reducer.mean(),
        'MODIS_ET': ee.Reducer.sum(),
        'FAO_ACTUAL_ET': ee.Reducer.sum(),
        'FAO_EVAPORATION': ee.Reducer.sum(),
        'FLDAS_BF_GW_RO': ee.Reducer.sum(),
        'FLDAS_SM': ee.Reducer.sum(),
        'USDA_CDL': ee.Reducer.first()
    }

    return gee_data_dict[data_name], gee_band_dict[data_name], gee_scale_dict[data_name], aggregation_dict[data_name]


def cloud_cover_filter(data_name, start_date, end_date, from_bit, to_bit):
    """
    Applies cloud cover mask on GEE data.

    :param data_name: Data Name.
           Valid dataset include- ['MODIS_Terra_NDVI', 'MODIS_Terra_EVI', 'MODIS_NDWI', 'VIIRS_NDVI',
           'VIIRS_EVI', 'VIIRS_EVI2'].
    :param start_date: Start date of data to download. Generated from download_gee_data() func.
    :param end_date: End date of data to download. Generated from download_gee_data() func.
    :param from_bit: Start bit to consider for masking.
    :param to_bit: End bit to consider for masking.

    :return: Cloud filtered imagecollection.
    """

    def bitwise_extract(img):
        """
        Applies cloudmask on image.
        :param Image.
        :return Cloud-masked image.
        """
        ee.Initialize()
        global qc_img
        if data_name in ('MODIS_Terra_NDVI', 'MODIS_Terra_EVI'):
            qc_img = img.select('DetailedQA')
        elif data_name in ('VIIRS_NDVI', 'VIIRS_EVI', 'VIIRS_EVI2'):
            qc_img = img.select('VI_Quality')
        elif data_name == 'MODIS_NDWI':
            qc_img = img.select('StateQA')

        masksize = ee.Number(1).add(to_bit).subtract(from_bit)
        mask = ee.Number(1).leftShift(masksize).subtract(1)
        apply_mask = qc_img.rightShift(from_bit).bitwiseAnd(mask).lte(1)
        return img.updateMask(apply_mask)

    if data_name in ('MODIS_Terra_NDVI', 'MODIS_Terra_EVI'):
        image = ee.ImageCollection('MODIS/061/MOD13Q1').filterDate(start_date, end_date)
        cloud_masked = image.map(bitwise_extract)
        return cloud_masked

    elif data_name in ('VIIRS_NDVI', 'VIIRS_EVI', 'VIIRS_EVI2'):
        image = ee.ImageCollection('NOAA/VIIRS/001/VNP13A1').filterDate(start_date, end_date)
        cloud_masked = image.map(bitwise_extract)
        return cloud_masked

    elif data_name == 'MODIS_NDWI':
        image = ee.ImageCollection('MODIS/061/MOD09A1').filterDate(start_date, end_date)
        cloud_masked = image.map(bitwise_extract)
        return cloud_masked


def download_gee_data(data_name, download_dir, year_list, month_range, merge_keyword, refraster=WestUS_raster,
                      grid_shape='../Data/shapefiles/Western_US/WestUS_gee_grid.shp'):
    """
    process and download data from GEE.

    :param data_name: Data name.
    Current valid data names are -
        ['SMAP_SM', 'LANDSAT_NDWI', 'LANDSAT_NDVI', 'GPM_PRECIP', 'GRIDMET_PRECIP', 'PRISM_PRECIP', 'VIIRS_NDVI',
        'VIIRS_EVI', 'VIIRS_EVI2', 'MODIS_Day_LST', 'MODIS_Terra_NDVI', 'MODIS_Terra_EVI', 'MODIS_NDWI', 'MODIS_LAI',
        'MODIS_ET', 'FAO_ACTUAL_ET', 'FAO_EVAPORATION', 'FLDAS_BF_GW_RO', 'FLDAS_SM']
    :param download_dir: File path of download directory.
    :param year_list: List of years to download data for.
    :param month_range: List of month ranges to download data for.
    :param merge_keyword: Keyword to use for merging downloaded data. Suggested 'WesternUS'/'Conus'.
    :param refraster: Reference raster to use for merging downloaded datasets.
    :param grid_shape: File path of grid shape for which data will be downloaded and mosaiced.

    :return: File path of downloaded raster data.
    """
    ee.Initialize()
    makedirs([download_dir])

    downloaded_raster_dict = {}
    for year in year_list:
        start_date = ee.Date.fromYMD(year, month_range[0], 1)
        end_date = ee.Date.fromYMD(year, month_range[1] + 1, 1)
        data, band, scale, reducer = get_gee_dict(data_name)

        if data_name in ('MODIS_Terra_NDVI', 'MODIS_Terra_EVI'):
            download_data = cloud_cover_filter(data_name, start_date, end_date, 0, 1).select(band).reduce(reducer). \
                multiply(scale).toFloat()

        elif data_name in ('VIIRS_NDVI', 'VIIRS_EVI', 'VIIRS_EVI2'):
            download_data = cloud_cover_filter(data_name, start_date, end_date, 0, 1).select(band).reduce(reducer). \
                multiply(scale).toFloat()

        elif data_name == 'MODIS_NDWI':
            nir = cloud_cover_filter(data_name, start_date, end_date, 0, 1).select(band[0]).reduce(reducer). \
                multiply(scale).toFloat()
            swir = cloud_cover_filter(data_name, start_date, end_date, 0, 1).select(band[1]).reduce(reducer). \
                multiply(scale).toFloat()
            download_data = nir.subtract(swir).divide(nir.add(swir))

        else:
            download_data = ee.ImageCollection(data).select(band).filterDate(start_date, end_date).reduce(reducer). \
                multiply(scale).toFloat()

        grids = gpd.read_file(grid_shape)['geometry']

        grid_no = 1
        for grid in grids:
            roi = grid.bounds
            gee_extent = ee.Geometry.Rectangle(roi)
            data_url = download_data.getDownloadURL({'name': data_name,
                                                     'crs': 'EPSG:4269',  # NAD83
                                                     'scale': scale,  # in meter. equal to ~0.02 deg
                                                     'region': gee_extent,
                                                     'format': 'GEO_TIFF'})
            key_word = data_name
            local_file_name = os.path.join(download_dir, f'{key_word}_{str(year)}_{str(grid_no)}.tif')
            print('Downloading', local_file_name, '.....')
            r = requests.get(data_url, allow_redirects=True)
            open(local_file_name, 'wb').write(r.content)
            grid_no += 1

        mosaic_name = f'{data_name}_{year}.tif'
        mosaic_dir = os.path.join(download_dir, f'{merge_keyword}')
        makedirs([mosaic_dir])
        downloaded_arr, downloaded_raster = mosaic_rasters(download_dir, mosaic_dir, mosaic_name, ref_raster=refraster,
                                                           search_by=f'*{year}*.tif', nodata=no_data_value)
        print('Downloaded Data Merged')
        downloaded_raster_dict[mosaic_name] = downloaded_raster

    return downloaded_raster_dict


def download_all_gee_data(data_list, download_dir, year_list, month_range, merge_keyword, refraster=WestUS_raster,
                          skip_download=False, copy_dir=None,
                          grid_shape='../Data/shapefiles/Western_US/WestUS_gee_grid.shp'):
    """
    Used to download all gee data together.

    :param data_list: List of valid data names to download.
    Current valid data names are -
        ['SMAP_SM', 'LANDSAT_NDWI', 'LANDSAT_NDVI', 'GPM_PRECIP', 'GRIDMET_PRECIP', 'PRISM_PRECIP', 'VIIRS_NDVI',
        'VIIRS_EVI', 'VIIRS_EVI2', 'MODIS_Day_LST', 'MODIS_Terra_NDVI', 'MODIS_Terra_EVI', 'MODIS_NDWI', 'MODIS_LAI',
        'MODIS_ET', 'FAO_ACTUAL_ET', 'FAO_EVAPORATION', 'FLDAS_BF_GW_RO', 'FLDAS_SM']
    :param download_dir: File path of main download directory. It will consist directory of individual dataset.
    :param year_list: List of year to download data for.
    :param month_range: Tuple of month ranges to download data for.
    :param merge_keyword: Keyword to use for merging downloded data. Suggested 'WesternUS'/'Conus'.
    :param refraster: Reference raster to use for merging downloaded datasets.
    :param skip_download: Set to True to skip download.
    :param copy_dir: File path to copy all downloaded data to a central directory.
    :param grid_shape: File path of grid shape for which data will be downloaded and mosaiced.

    :return: None
    """
    global downloaded_raster

    download_dir_dict = {}

    if not skip_download:
        for data_name in data_list:
            data_download_dir = os.path.join(download_dir, data_name)
            makedirs([data_download_dir])

            downloaded_dict = download_gee_data(data_name, data_download_dir, year_list, month_range, merge_keyword,
                                                refraster, grid_shape)

            for key, val in downloaded_dict.items():
                copied_file = copy_file(val, copy_dir, rename=None)
                name = key[:key.rfind('.')]
                download_dir_dict[name] = copied_file
    else:
        pass


def download_ssebop_et(years_list, month_range_list, download_dir='../Data/GEE_data/Ssebop_monthly_ETa',
                       ssebop_link='https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/uswem/web/conus/eta'
                                   '/modis_eta/monthly/downloads/', skip_download=False):
    """
    Download ssebop actual ET data (unit in mm).

    :param years_list: List of years for which to download data.
    :param month_range_list: List of first and last month, i.e., to download data from April-September use [4, 9].
    :param download_dir: Directory path to download data.
    :param ssebop_link: USGS link with ssebop ET data.
    :param skip_download: Set to True to skip download.

    :return: None.
    """
    makedirs([download_dir])
    if not skip_download:
        months_list = [m for m in range(month_range_list[0], month_range_list[1] + 1)]

        year_month_combs = list(itertools.product(years_list, months_list))

        for each in year_month_combs:
            year, month = each
            ssebop_et_link = f'{ssebop_link}m{str(year)}0{str(month)}.zip'
            r = requests.get(ssebop_et_link, allow_redirects=True)

            download_name = ssebop_et_link[ssebop_et_link.rfind('/') + 1:]
            download_to = os.path.join(download_dir, download_name)

            open(download_to, 'wb').write(r.content)

        zipped_files = extract_data(download_dir, download_dir, search_by='*.zip', rename_file=True)
        for z in zipped_files:
            os.remove(z)


def download_all_datasets(year_list, gee_data_list=None, skip_download_gee_data=True, skip_download_ssebop_data=True):
    """
    Download all GEE datasets and ssebop data.

    :param year_list: List of year to download data for. We will use data for [2010, 2015] in the model.
    :param gee_data_list: List of data to download from GEE. Default set to None, use if skip_download_gee_data=True.
                          Datasets currently used in the model:
                          ['MODIS_NDWI', 'GPM_PRECIP', 'MODIS_Day_LST', 'PRISM_PRECIP']
    :param skip_download_gee_data: Set to False if want to download listed data. Default set to True.
    :param skip_download_ssebop_data: Set to False if want to download ssebop data. Default set to True.

    :return: None.
    """
    download_all_gee_data(gee_data_list, download_dir='../Data/GEE_data', year_list=year_list, month_range=[4, 9],
                          merge_keyword='WestUS', refraster=WestUS_raster, skip_download=skip_download_gee_data,
                          copy_dir='../Data/Compiled_data',
                          grid_shape='../Data/shapefiles/Western_US/WestUS_gee_grid.shp')

    download_ssebop_et(year_list, month_range_list=[4, 9], download_dir='../Data/GEE_data/Ssebop_monthly_ETa',
                       skip_download=skip_download_ssebop_data)


def process_cdl_data(cdl_dir='../Data/GEE_data/USDA_CDL', processed_dir='../Data/GEE_data/USDA_CDL/WestUS',
                     westUS_shape='../Data/shapefiles/Western_US/WestUS.shp', ref_raster=WestUS_raster,
                     skip_processing=False):
    """
    Crops CDL data for Western US and reclassifies it to crop vs non-crop and developed vs non-developed datasets.

    Developed classes: 121, 122, 123, 124
    non-crop classes : 58, 59, 60, 61, 63, 64, 65, 81, 82, 83, 87, 88, 111, 121, 122, 123, 124, 131, 141, 142, 143,
                       152, 176, 190, 195
    details in: https://developers.google.com/earth-engine/datasets/catalog/USDA_NASS_CDL
    CDL data download link : https://www.nass.usda.gov/Research_and_Science/Cropland/Release/

    :param cdl_dir: Directory path of original (whole US) CDL datasets.
    :param processed_dir: File path of directory to save processed data.
    :param westUS_shape: Western US shapefile.
    :param ref_raster: File path of reference raster. Default set to WesternUS 2km reference raster.
    :param skip_processing: Set to True to skip processing.

    :return: Dictionaries of file paths of processed crop vs non-crop and developed vs non-developed datasets.
    """
    crop_data_dict, developed_data_dict = None, None

    if not skip_processing:
        makedirs([processed_dir])
        cdl_US = glob(os.path.join(cdl_dir, '*.tif'))

        crop_data_dict = {}
        developed_data_dict = {}

        for cdl_ras in cdl_US:
            westus_cdl = clip_resample_reproject_raster(cdl_ras, westUS_shape, keyword='WestUS',
                                                        output_raster_dir=processed_dir, clip_and_resample=True,
                                                        targetaligned=False, resample_algorithm='near',
                                                        resolution=model_res, crs='EPSG:4269',
                                                        output_datatype=gdal.GDT_Byte)

            # converting to crop vs non-crop and developed vs non-developed data
            noncrop_classes = [58, 59, 60, 61, 63, 64, 65, 81, 82, 83, 87, 88, 111, 121, 122, 123, 124, 131, 141, 142,
                               143, 152, 176, 190, 195]

            year = os.path.splitext(os.path.basename(westus_cdl))[0].split('_')[1]
            cdl_arr = read_raster_arr_object(westus_cdl, get_file=False)
            ref_arr, ref_file = read_raster_arr_object(ref_raster)

            # crop vs non-crop raster
            crop_arr = np.where(np.isin(cdl_arr, noncrop_classes), ref_arr, 1)
            crop_raster_path = os.path.join(processed_dir, f'USDA_cropland_{year}.tif')
            crop_output_file = write_array_to_raster(crop_arr, ref_file, ref_file.transform, crop_raster_path)

            # developed vs non-developed
            dev_arr = np.where(cdl_arr == 121, 1, ref_arr)
            dev_arr = np.where(cdl_arr == 122, 2, dev_arr)
            dev_arr = np.where(cdl_arr == 123, 3, dev_arr)
            dev_arr = np.where(cdl_arr == 124, 4, dev_arr)

            dev_raster_path = os.path.join(processed_dir, f'USDA_developed_{year}.tif')
            dev_output_file = write_array_to_raster(dev_arr, ref_file, ref_file.transform, dev_raster_path)

            crop_output_file = copy_file(crop_output_file, copy_dir='../Data/Compiled_data')
            data_name = crop_output_file[crop_output_file.rfind(os.sep) + 1:crop_output_file.rfind('.')]
            crop_data_dict[data_name] = crop_output_file

            dev_output_file = copy_file(dev_output_file, copy_dir='../Data/Compiled_data')
            data_name = dev_output_file[dev_output_file.rfind(os.sep) + 1:dev_output_file.rfind('.')]
            developed_data_dict[data_name] = dev_output_file

        pickle.dump(crop_data_dict, open('../Data/Compiled_data/crop_data_dict.pkl', mode='wb+'))
        pickle.dump(developed_data_dict, open('../Data/Compiled_data/developed_land_data_dict.pkl', mode='wb+'))

    else:
        crop_data_dict = pickle.load(open('../Data/Compiled_data/crop_data_dict.pkl', mode='rb'))
        developed_data_dict = pickle.load(open('../Data/Compiled_data/developed_land_data_dict.pkl', mode='rb'))

    return crop_data_dict, developed_data_dict


def process_ssebop_data(years=(2010, 2015), ssebop_dir='../Data/GEE_data/Ssebop_monthly_ETa',
                        output_dir_conus='../Data/GEE_data/Ssebop_monthly_ETa/conus',
                        output_dir_ssebop='../Data/GEE_data/Ssebop_monthly_ETa/WesternUS',
                        westUS_shape='../Data/shapefiles/Western_US/WestUS.shp', skip_processing=False):
    """
    Process (sum and clip to Western US extent) Ssebop ET.

    :param years: Tuple/list of years for which ssebop data was downloaded.
    :param ssebop_dir: Directory file path of downloaded ssebop datasets.
    :param output_dir_conus: File path of directory to save conus summed ET for each year.
    :param output_dir_ssebop: File path of directory to save summed ET for each year at Western US extent.
    :param westUS_shape: Filepath of Western US shapefile.
    :param skip_processing: Set to True if want to skip ssebop processing.

    :return: A dictionary with ssebop data file paths.
    """
    if not skip_processing:
        makedirs([output_dir_conus, output_dir_ssebop])

        ssebop_data_dict = {}
        for year in years:
            print(f'Processing Ssebop data for {year}')
            ssebop_datasets = glob(os.path.join(ssebop_dir, f'*{year}*.tif'))
            ssebop_ref_arr = read_raster_arr_object(ssebop_datasets[0], get_file=False)
            et_sum_arr = np.zeros(ssebop_ref_arr.shape)

            for data in ssebop_datasets:
                ssebop_arr, ssebop_file = read_raster_arr_object(data)
                et_sum_arr += ssebop_arr

            et_sum_arr = np.where(ssebop_ref_arr == no_data_value, no_data_value, et_sum_arr)

            # saving summed raster at conus extent
            output_name = f'SSEBOP_ET_{year}.tif'
            output_raster_conus = os.path.join(output_dir_conus, output_name)
            conus_raster = write_array_to_raster(et_sum_arr, ssebop_file, ssebop_file.transform, output_raster_conus)

            # clipping to Western US extent
            output_file = clip_resample_reproject_raster(conus_raster, westUS_shape, keyword=' ',
                                                         clip=False, resample=False, clip_and_resample=True,
                                                         targetaligned=False, resolution=model_res,
                                                         output_raster_dir=output_dir_ssebop)

            output_file = copy_file(output_file, copy_dir='../Data/Compiled_data')
            ssebop_data_dict[output_name[:output_name.rfind('.')]] = output_file

            pickle.dump(ssebop_data_dict, open('../Data/Compiled_data/ssebop_dict.pkl', mode='wb+'))
    else:
        ssebop_data_dict = pickle.load(open('../Data/Compiled_data/ssebop_dict.pkl', mode='rb'))

    return ssebop_data_dict


def run_all_preprocessing(skip_cdl_processing=False, skip_ssebop_processing=False):
    """
    Run all preprocessing steps.

    :param skip_cdl_processing: Set True if want to skip cdl data preprocessing.
    :param skip_ssebop_processing: Set True if want to skip ssebop data preprocessing.

    :return: Dictionaries of crop and developed land use data file paths
    """
    crop_data_dict, developed_data_dict = process_cdl_data(skip_processing=skip_cdl_processing)
    ssebop_dict = process_ssebop_data(skip_processing=skip_ssebop_processing)

    return crop_data_dict, developed_data_dict, ssebop_dict


def compile_observed_pumping_data(data_dir='../Data/USGS_water_use_data', search_by='*201[0-5]*.xlsx',
                                  county_shape='../Data/shapefiles/Western_US/WestUS_county.shp',
                                  output_csv='../Data/USGS_water_use_data/WestUS_county_gw_use.csv',
                                  skip_compiling=True):
    """
    Compile county-wide groundwater use data for Western US.

    :param data_dir: Directory path of yearly groundwater data excels.
    :param search_by: Search pattern for yearly data excels. Default set to '*201[0-5]*.xlsx' for selecting 2010 and
                      2015 data only.
    :param county_shape: File path of Western US county shapefile location.
    :param output_csv: File path to save output csv.
    :param skip_compiling: Set to False to compile pumping data. Default set to True (data already compiled).

    :return: Saves compiled
    """
    if not skip_compiling:
        wateruse_data = glob(os.path.join(data_dir, search_by))
        county_df = gpd.read_file(county_shape)

        county_wateruse = pd.DataFrame()
        for data in wateruse_data:
            wateruse_df = pd.read_excel(data, sheet_name='CountyData')
            wateruse_df = wateruse_df[['COUNTY', 'STATE', 'COUNTYFIPS', 'FIPS', 'YEAR', 'TO-WGWFr']]

            joined_df = county_df.merge(wateruse_df, left_on='fips', right_on='FIPS', how='inner')
            county_wateruse = pd.concat([county_wateruse, joined_df])

        # converting groundwater withdrawal from Mgal/day to mm/year.
        county_wateruse['gw_withdrawal'] = 1000 * (1e6 * county_wateruse['TO-WGWFr'] * 0.00378541 * 365 /
                                                   county_wateruse['area_m2'])

        county_wateruse = county_wateruse[['NAME', 'fips', 'YEAR', 'gw_withdrawal']]
        county_wateruse_df = county_wateruse.rename(columns={'NAME': 'Name', 'fips': 'fips', 'YEAR': 'Year',
                                                             'gw_withdrawal': 'total_gw_observed'})
        county_wateruse_df.to_csv(output_csv, index=False)

    else:
        pass
