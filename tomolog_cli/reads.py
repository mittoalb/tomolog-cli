import os
import h5py

import numpy as np

from tomolog_cli import log
from tomolog_cli import utils

__author__ = "Viktor Nikitin"
__copyright__ = "Copyright (c) 2022, UChicago Argonne, LLC."
__docformat__ = 'restructuredtext en'
__all__ = ['read_scan_info', 'read_raw', 'read_recon']


def read_scan_info(args):
    '''Read acquistion parameters from an hdf5 file

    Parameters
    ----------
    args.file_name : string
        The raw data tomography hdf file name

    Returns
    -------
    meta
        Dictionary containing all hdf file stored experiment meta data
    '''
    _, meta = utils.read_hdf_meta(args.file_name, add_shape=True)

    return meta


def read_raw(args):
    '''Read raw data from an hdf5 file

    Parameters
    ----------
    args.file_name : string
        The raw data tomography hdf file name

    Returns
    -------
    proj
        list of ndarray(s) containing the first data set projection of 
        each data set stored in the hdf file. Usually proj contains only
        one image but in some nano CT measurement it may also contain 
        a micro CT measurement of the same sample

    '''
    proj = []
    with h5py.File(args.file_name) as fid:
        log.info('Reading CT projection')
        if args.double_fov == True:
            log.warning('hanling the data set as a double FOV')
            image_0 = np.flip(fid['exchange/data'][0][:], axis=1)
            image_1 = fid['exchange/data'][-1][:]
            data = np.hstack((image_0, image_1))
        else:
            data = fid['exchange/data'][0][:]
        proj.append(data)
        log.info('Reading CT projection')
        try:
            proj.append(fid['exchange/data2'][0][:])
            log.info('Reading microCT projection')
        except:            
            pass
    return proj


def read_recon(args, meta):
    '''Read reconstructed ortho-slices

    Parameters
    ----------
    args.file_name : string
        The raw data tomography hdf file name
    args.rec_type
        Prefix of the recon folder choices: recgpu,rec
    args.idx
        Id of x slice for reconstruction visualization
    args.idy
        Id of y slice for reconstruction visualization
    args.idz
        Id of z slice for reconstruction visualization
    meta
        Dictionary containing all hdf file stored experiment meta data    

    Returns
    -------
    recon : list
        List containing 3 orthogonal (x, y, z) slices through the sample
    binning_rec : int
        Binning factor calculated by comparing raw image width and recon size
    '''

    data_size     = 'exchange_data'
    binning       = 'measurement_instrument_detector_binning_x'

    dims          = meta[data_size][0].replace("(", "").replace(")", "").split(',')
    width         = int(dims[2])
    height        = int(dims[1])
    binning       = int(meta[binning][0])

    recon = []
    binning_rec = -1
    
    try:
        basename = os.path.basename(args.file_name)[:-3]
        dirname = os.path.dirname(args.file_name)
        # shift from the middle
        shift = 0
        # set the correct prefix to find the reconstructions
        rec_prefix = 'r'
        if args.rec_type == 'rec':
            rec_prefix = 'recon'

        top = os.path.join(dirname+'_'+args.rec_type, basename+'_rec')
        tiff_file_list = list(filter(lambda x: x.endswith(('.tif', '.tiff')), os.listdir(top)))
        z_start = int(tiff_file_list[0].split('.')[0].split('_')[1])
        z_end   = int(tiff_file_list[-1].split('.')[0].split('_')[1]) + 1
        height = z_end-z_start
        fname_tmp = os.path.join(top, tiff_file_list[0])
        # print(z_start, z_end, height, width)
        # print(fname_tmp)
        # take size
        tmp = utils.read_tiff(fname_tmp).copy()
        binning_rec = width//tmp.shape[0]
        # print(binning_rec)
        w = width//binning_rec
        h = height//binning_rec

        args.idz = int(h//2+shift)
        args.idy = int(w//2+shift)
        args.idx = int(w//2+shift)

        z = utils.read_tiff(
            f'{dirname}_{args.rec_type}/{basename}_rec/{rec_prefix}_{args.idz:05}.tiff').copy()
        # read x,y slices by lines
        y = np.zeros((h, w), dtype='float32')
        x = np.zeros((h, w), dtype='float32')
        for j in range(z_start, z_end//binning_rec):
            zz = utils.read_tiff(
                f'{dirname}_{args.rec_type}/{basename}_rec/{rec_prefix}_{j:05}.tiff')
            y[j-z_start, :] = zz[args.idy]
            x[j-z_start, :] = zz[:, args.idx]

        recon = [x,y,z]
        log.info('Adding reconstruction')
    except:
        log.warning('Skipping reconstruction')

    return recon, binning_rec