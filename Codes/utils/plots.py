import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from Codes.utils.system_ops import makedirs
from Codes.utils.stats_ops import calculate_r2


def scatter_plot_of_same_vars(Y_pred, Y_obsv, x_label, y_label, plot_name, savedir, alpha=0.1,
                              color_format='o', marker_size=0.5, title=None,
                              axis_lim=None, tick_interval=50):
    """
    Makes scatter plot of model prediction vs observed data.

    :param Y_pred: flattened prediction array.
    :param Y_obsv: flattened observed array.
    :param x_label: Str of x label.
    :param y_label: Str of y label.
    :param plot_name: Str of plot name.
    :param savedir: filepath to save the plot.
    :param alpha: plot/scatter dots transparency level.
    :param marker_size: (float or int) Marker size.
    :param color_format: Color and plot type format. For example, for 'bo' 'b' means blue color and 'o' means dot plot.
    :param title: Str of title. Default set to None.
    :param axis_lim: A list of minimum and maximum values of x and y axis.
                     Default set to None (will calculate and set xlim, ylim itself)
    :param tick_interval: X and Y tick intervals to plot.
                          Default set to 50 for units of mm/month. For annual model use fraction.

    :return: A scatter plot of model prediction vs observed data.
    """
    # calculating min and max value ranges of the variables
    min_value = min(Y_pred.min(), Y_obsv.min())
    max_value = max(Y_pred.max(), Y_obsv.max())

    plt.rcParams.update({'font.size': 18})
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.set_facecolor('none')

    ax.plot(Y_obsv, Y_pred, color_format, alpha=alpha, markersize=marker_size)
    ax.plot([min_value, max_value], [min_value, max_value], '-r', linewidth=2)
    ax.set_xlabel(x_label)  # 'Observed'
    ax.set_ylabel(y_label)  # 'Predicted'

    if axis_lim:
        ax.set_xlim(axis_lim)
        ax.set_ylim(axis_lim)
    else:
        ax.set_xlim([min_value, max_value])
        ax.set_ylim([min_value, max_value])
        ax.set_xticks(np.arange(0, max_value, tick_interval))
        ax.set_yticks(np.arange(0, max_value, tick_interval))

    if title is not None:
        ax.set_title(title)

    r2_val = round(calculate_r2(Y_pred, Y_obsv), 4)
    ax.text(0.1, 0.9, s=f'$R^2={r2_val:.3f}$', transform=ax.transAxes)

    makedirs([savedir])

    fig_loc = os.path.join(savedir, plot_name)
    fig.savefig(fig_loc, dpi=300)


def density_grid_plot_of_same_vars(Y_pred, Y_obsv, x_label, y_label, plot_name, savedir,
                                   bins=300, title=None,
                                   axis_lim=None, tick_interval=50):
    """
    Makes density grid plot for model prediction vs observed data. In the density grid plot, each grid represents a bin
    and each bin value represents the number/fraction of point in that bin.

    :param Y_pred: flattened prediction array.
    :param Y_obsv: flattened observed array.
    :param x_label: Str of x label.
    :param y_label: Str of y label.
    :param plot_name: Str of plot name.
    :param savedir: filepath to save the plot.
    :param bins: Numbers of bins to consider while binning for density grid. Default set to 300.
    :param title: Str of title. Default set to None.
    :param axis_lim: A list of minimum and maximum values of x and y axis.
                     Default set to None (will calculate and set xlim, ylim itself)
    :param tick_interval: X and Y tick intervals to plot.
                      Default set to 50 for units of mm/month. For annual model use fraction.

    :return: A scatter plot of model prediction vs observed data.
    """
    # calculating min and max value ranges of the variables
    min_value = min(Y_pred.min(), Y_obsv.min())
    max_value = max(Y_pred.max(), Y_obsv.max())

    # creating a density grid for the dataset where each point belongs to a bin. The outputs of the np.histogram2d are
    # numpy arrays
    heatmap, xedges, yedges = np.histogram2d(Y_obsv, Y_pred, bins=bins, density=False)

    plt.rcParams.update({'font.size': 18})
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.set_facecolor('none')

    # Creating a custom colormap: white for low values, transitioning to colors for higher densities
    plasma_cmap = plt.get_cmap('viridis')
    white = np.array([1, 1, 1, 1])  # # Modify the white color to include an alpha channel (RGBA format)
    custom_cmap = ListedColormap(
        np.vstack((white, plasma_cmap(np.linspace(0, 1, 256)))))  # Stack the white color with the plasma colormap

    # Plot the density grid as a heatmap
    # plt.imshow() expects data in the format where the rows of the matrix correspond to the y-axis and
    # the columns correspond to the x-axis
    # However, np.histogram2d() returns the 2D array (heatmap) such that the first dimension corresponds to the x-axis
    # (observed values) and the second dimension corresponds to the y-axis (predicted values).
    # So, we use heatmap.T
    extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
    density_plot = ax.imshow(heatmap.T, origin='lower', cmap=custom_cmap, aspect='auto', extent=extent)

    ax.set_xlabel(x_label, fontsize=18)  # 'Observed'
    ax.set_ylabel(y_label, fontsize=18)  # 'Predicted'

    ax.plot([min_value, max_value], [min_value, max_value], '-r', linewidth=2)

    ax.tick_params(axis='both', labelsize=18)

    cbar = fig.colorbar(mappable=density_plot)
    cbar.ax.tick_params(labelsize=18)
    cbar.set_label('Number of samples in each bin', size=18)

    plt.tight_layout()

    if axis_lim:
        ax.set_xlim(axis_lim)
        ax.set_ylim(axis_lim)
    else:
        ax.set_xlim([min_value, max_value])
        ax.set_ylim([min_value, max_value])
        ax.set_xticks(np.arange(0, max_value, tick_interval))
        ax.set_yticks(np.arange(0, max_value, tick_interval))

    if title is not None:
        ax.set_title(title)

    r2_val = round(calculate_r2(Y_pred, Y_obsv), 3)
    ax.text(0.1, 0.9, s=f'$R^2={r2_val:.3f}$', transform=ax.transAxes, color='black')

    makedirs([savedir])

    fig_loc = os.path.join(savedir, plot_name)
    fig.savefig(fig_loc, dpi=300)


def scatter_plot(X, Y, x_label, y_label, plot_name, savedir, alpha=0.1,
                  color_format='o', marker_size=0.5, title=None):
    """
    Makes scatter plot between 2 variables.

    :param X: Variable array in x axis.
    :param Y: Variable array in y axis.
    :param x_label: Str of x label.
    :param y_label: Str of y label.
    :param plot_name: Str of plot name.
    :param savedir: filepath to save the plot.
    :param alpha: plot/scatter dots transparency level.
    :param marker_size: (float or int) Marker size.
    :param color_format: Color and plot type format. For example, for 'bo' 'b' means blue color and 'o' means dot plot.
    :param title: Str of title. Default set to None.
    :param axis_lim: A list of minimum and maximum values of x and y axis.
                     Default set to None (will calculate and set xlim, ylim itself)

    :return: A scatter plot of model prediction vs observed data.
    """
    plt.rcParams.update({'font.size': 18})
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(X, Y, color_format, alpha=alpha, markersize=marker_size)
    ax.plot([0, 1], [0, 1], '-r', transform=ax.transAxes)
    ax.set_xlabel(x_label)  # 'Observed'
    ax.set_ylabel(y_label)  # 'Predicted'

    if title is not None:
        ax.set_title(title)

    if savedir is not None:
        makedirs([savedir])

        fig_loc = os.path.join(savedir, plot_name)
        fig.savefig(fig_loc, dpi=300)
