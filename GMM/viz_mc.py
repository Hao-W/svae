import matplotlib.gridspec as gridspec
import matplotlib.pyplot as plt
from plots import plot_cov_ellipse
import torch
import numpy as np

class Viz_MC:
    """
    A class which visualizes the prediction as a Markov chain
        Plot_onestep : visualize the data/sample in one time Step
        Plot_chains : align all visualizaztion of all datasets in different rows
    """
    def __init__(self, K, viz_interval, fs, title_fontsize, ob_ms, opacity, bound, colors):
        super().__init__()
        self.K = K
        self.viz_interval = viz_interval
        self.fs = fs
        self.title_fontsize = title_fontsize
        self.ob_ms = ob_ms
        self.opacity = opacity
        self.bound = bound
        self.colors = colors
    def Plot_onestep(self, ax, ob, latents=None):
        if latents == None:
            ax.scatter(ob[:, 0], ob[:, 1], c='k', s=self.ob_ms, zorder=3)
        else:
            (tau, mu, state) = latents
            sigma2 = 1. / tau

            assignments = state.argmax(-1)
            for k in range(self.K):
                cov_k = np.diag(sigma2[k])
                ob_k = ob[np.where(assignments == k)]
                ax.scatter(ob_k[:, 0], ob_k[:, 1], c=self.colors[k], s=self.ob_ms, zorder=3)
                plot_cov_ellipse(cov=cov_k, pos=mu[k], nstd=2, color=self.colors[k], ax=ax, alpha=self.opacity, zorder=3)
        ax.set_ylim([-self.bound, self.bound])
        ax.set_xlim([-self.bound, self.bound])
        ax.set_xticks([])
        ax.set_yticks([])

    # def Plot_chains(self, data_list, sample_lists, elbo_lists, ess_lists, sample_size):
    #     ## initialize figure object
    #     num_rows = len(data_list)
    #     num_steps = len(sample_lists[0])
    #     num_cols_sample = 2 + int((num_steps - 1) / self.viz_interval)
    #     num_cols = 1 + 2 + num_cols_sample
    #     # outer_gs = gridspec.GridSpec()
    #     outer_gs = gridspec.GridSpec(num_rows, num_cols)
    #     sample_gs = gridspec.GridSpecFromSubplotSpec(num_rows, num_cols_sample, subplot_spec=outer_gs[:, :num_cols_sample], wspace=0, hspace=0)
    #     converge_gs = gridspec.GridSpecFromSubplotSpec(num_rows, 2, subplot_spec=outer_gs[:, num_cols_sample:], wspace=0.2, hspace=0.2)
    #     fig = plt.figure(figsize=(self.fs, self.fs * num_rows / num_cols))
    #     plt.rc('axes',edgecolor='#eeeeee')
    #     for row_ind, sample_list in enumerate(sample_lists):
    #         data = data_list[row_ind].data.numpy()
    #         ax = fig.add_subplot(sample_gs[row_ind, 0])
    #         self.Plot_onestep(ax, data) ## visualize raw dataset in the 1st column
    #         if row_ind == 0:
    #             ax.set_title('Data', fontsize=self.title_fontsize)
    #         col_ind = 1
    #         for i in range(0, num_steps, self.viz_interval):
    #             ax = fig.add_subplot(sample_gs[row_ind, col_ind])
    #             self.Plot_onestep(ax, data, latents=sample_list[i]) ## visualize raw dataset in the 1st column
    #             if row_ind == 0:
    #                 if i == 0:
    #                     ax.set_title('One-shot', fontsize=self.title_fontsize)
    #                 else:
    #                     ax.set_title('Step %d' % i, fontsize=self.title_fontsize)
    #             col_ind += 1
    #         col_ind += 1 ## leave that columen as whitespace
    #         ## plot ELBO and ESS
    #         ax1 = fig.add_subplot(converge_gs[row_ind, 0])
    #         ax2 = fig.add_subplot(converge_gs[row_ind, 1])
    #         ax1.plot(elbo_lists[row_ind].data.numpy(), c=self.colors[0])
    #         ax2.plot(ess_lists[row_ind].data.numpy(), c=self.colors[-1])
    #         # ax1.set_title('Dataset %d' % (row_ind+1))
    #         if row_ind == 0:
    #             ax1.set_title('ELBO', fontsize=self.title_fontsize)
    #             ax2.set_title('ESS (L = %d)' % sample_size, fontsize=self.title_fontsize)
    #
    #
    #
    def Plot_chains(self, data_list, sample_lists, filename):
        ## initialize figure object
        num_rows = len(data_list)
        num_steps = len(sample_lists[0])
        num_cols = 2 + int((num_steps - 1) / self.viz_interval)
        gs = gridspec.GridSpec(num_rows, num_cols)
        gs.update(left=0.05 , bottom=0.05, right=0.95, top=0.95, wspace=0, hspace=0)
        fig = plt.figure(figsize=(self.fs, self.fs * num_rows / num_cols))
        plt.rc('axes',edgecolor='#eeeeee')
        for row_ind, sample_list in enumerate(sample_lists):
            data = data_list[row_ind].data.numpy()
            ax = fig.add_subplot(gs[row_ind, 0])
            self.Plot_onestep(ax, data) ## visualize raw dataset in the 1st column
            if row_ind == 0:
                ax.set_title('Data', fontsize=self.title_fontsize)
            col_ind = 1
            for i in range(0, num_steps, self.viz_interval):
                ax = fig.add_subplot(gs[row_ind, col_ind])
                self.Plot_onestep(ax, data, latents=sample_list[i]) ## visualize raw dataset in the 1st column
                if row_ind == 0:
                    if i == 0:
                        ax.set_title('One-shot', fontsize=self.title_fontsize)
                    else:
                        ax.set_title('Step %d' % i, fontsize=self.title_fontsize)
                col_ind += 1
        plt.savefig(filename + '.svg', dpi=300)
        plt.savefig(filename + '.pdf')

    def Plot_metrics(self, log_joint_lists, ess_lists, sample_size, filename):
        num_cols = len(log_joint_lists)
        gs = gridspec.GridSpec(2, num_cols)
        gs.update(left=0.05 , bottom=0.05, right=0.95, top=0.95, wspace=0.2, hspace=0.05)
        fig = plt.figure(figsize=(self.fs, self.fs * 2 / num_cols))
        plt.rc('axes',edgecolor='#eeeeee')
        for col_ind in range(num_cols):
            ax1 = fig.add_subplot(gs[0, col_ind])
            ax2 = fig.add_subplot(gs[1, col_ind])
            # ax3 = fig.add_subplot(gs[2, col_ind])
            temp = log_joint_lists[col_ind].data.numpy()

            baseline = np.ones(temp.shape[0]) * temp[0]
            ax1.plot(log_joint_lists[col_ind].data.numpy(), c=self.colors[0], marker='o')
            ax1.plot(baseline, '--', c=self.colors[1], alpha=0.4)

            # ax2.plot(elbo_lists[col_ind].data.numpy(), c=self.colors[1], marker='o')
            ax2.plot(ess_lists[col_ind].data.numpy() / sample_size, c=self.colors[2])
            ax2.scatter(np.arange(temp.shape[0]), ess_lists[col_ind].data.numpy() / sample_size, c=self.colors[2], s=6.0)

            # ax1.set_title('N= %d' % ((col_ind+1) * 20), fontsize=self.title_fontsize)
            # if col_ind == 0:
                # ax1.set_ylabel('log p(z, x)', fontsize=self.title_fontsize)
                # ax2.set_ylabel('ELBO', fontsize=self.title_fontsize)
                # ax2.set_ylabel('ESS / L', fontsize=self.title_fontsize)
            ax2.set_ylim([-0.1, 1.1])
            ax1.set_xticks([])
            ax1.set_ylim([temp.min()-50, temp.max()+10])
        plt.savefig(filename + '.svg', dpi=300)
        plt.savefig(filename + '.pdf')