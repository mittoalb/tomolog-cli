import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patheffects as PathEffects

from matplotlib_scalebar.scalebar import ScaleBar
from mpl_toolkits.axes_grid1 import make_axes_locatable

from tomolog_cli import utils

def plot_projection(proj, fname, resolution):
    '''Plot the first projection with a scalebar and colorbar, and save it to FILENAME_PROJ
    '''

    # auto-adjust colorbar values according to a histogram
    mmin, mmax = utils.find_min_max(proj, 0.005)
    proj[proj > mmax] = mmax
    proj[proj < mmin] = mmin

    # plot
    fig = plt.figure(constrained_layout=True, figsize=(6, 4))
    ax = fig.add_subplot()
    im = ax.imshow(proj, cmap='gray')
    # Create scale bar
    scalebar = ScaleBar(resolution, "um", length_fraction=0.25)
    ax.add_artist(scalebar)
    # txt.set_path_effects([PathEffects.withStroke(linewidth=1, foreground='w')])
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.1)
    plt.colorbar(im, cax=cax)
    # plt.show()
    # save
    plt.savefig(fname, bbox_inches='tight', pad_inches=0, dpi=300)
    plt.cla()
    plt.close(fig)



def plot_recon(args, dims, recon, fname, resolution, binning):
    '''Plot orthoslices with scalebars and colorbars, and save the figure as FILENAME_RECON
    '''
    
    width         = int(dims[2])
    height        = int(dims[1])

    fig = plt.figure(constrained_layout=True, figsize=(6, 12))
    grid = fig.add_gridspec(3, 1, height_ratios=[
                            1, 1, width/height])
    slices = ['x', 'y', 'z']
    # autoadjust colorbar values according to a histogram

    if args.min==args.max:
        args.min, args.max = utils.find_min_max(np.concatenate(recon), args.scale)

    # plot 3 slices in a column
    w = width//binning
    h = height//binning

    sl = [args.idx,args.idy,args.idz]#params['id'+slices[k]]
    for k in range(3):
        recon[k][recon[k] > args.max] = args.max
        recon[k][recon[k] < args.min] = args.min
        ax = fig.add_subplot(grid[k])
        im = ax.imshow(recon[k], cmap='gray')
        # Create scale bar
        scalebar = ScaleBar(resolution, "um", length_fraction=0.25)
        ax.add_artist(scalebar)
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="5%", pad=0.1)
        plt.colorbar(im, cax=cax)
        #sl = params['id'+slices[k]]
        ax.set_ylabel(f'slice {slices[k]}={sl[k]}', fontsize=14)

    # plt.show()
    # save
    plt.savefig(fname, bbox_inches='tight', pad_inches=0, dpi=300)
    plt.cla()
    plt.close(fig)