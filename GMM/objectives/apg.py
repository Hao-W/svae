import torch
import torch.nn as nn
from utils import *
from normal_gamma import *
from forward_backward import *
from forward_backward_test import *
import probtorch
"""
EUBO : loss function is  E_{p(z'|x)}[KL(p(z | z', x) || q_\f(z | z', x))]
                        + E_{p(z|x)}[KL(p(z' | z, x) || q_\f(z' | z, x))]
init_eta : initialize eta as the first step

"""

def APG(models, ob, mcmc_steps):
    """
    Learn both forward kernels f_z, f_eta and backward kernels b_z, b_eta,
    involving gradient of EUBO and ELBO w.r.t forward parameters and backward
    parameters respectively, in order to NOT use REINFORCE or Reparameterization.
    """
    metrics = {'loss' : [], 'ess' : []}
    (os_eta, f_z, f_eta, b_z, b_eta) = models
    loss_os, ess_os, w_z, ob_tau, ob_mu, z = Init_eta(os_eta, f_z, ob)
    metrics['loss'].append(loss_os.unsqueeze(0))
    metrics['ess'].append(ess_os.unsqueeze(0))
    for m in range(mcmc_steps):
        if m == 0:
            z = Resample(z, w_z, idw_flag=False) ## resample state
        else:
            z = Resample(z, w_z, idw_flag=True)
        loss_eta, ess_eta, w_eta, ob_tau, ob_mu = Update_eta(f_eta, b_eta, ob, z, ob_tau, ob_mu)
        ob_tau = Resample(ob_tau, w_eta, idw_flag=True) ## resample precisions
        ob_mu = Resample(ob_mu, w_eta, idw_flag=True) ## resample centers
        loss_z, ess_z, w_z, z = Update_z(f_z, b_z, ob, ob_tau, ob_mu, z) ## update cluster assignments
        metrics['loss'].append((loss_eta + loss_z).unsqueeze(0))
        metrics['ess'].append((ess_eta + ess_z).unsqueeze(0) / 2)
    reused = (z)
    return metrics, reused

def ELBO(models, obs, SubTest_Params):
    """
    The stepwise elbo
    """
    (device, sample_size, batch_size, N, K, D, mcmc_size) = SubTest_Params
    # eubos = torch.zeros(mcmc_size+1).cuda().to(device)
    esss = torch.zeros(mcmc_size+1).cuda().to(device)
    DBs_eta = []
    DBs_z = []
    ELBOs = []
    ESSs = []
    LLs = []
    (oneshot_eta, enc_eta, enc_z) = models
    model_os = (oneshot_eta, enc_z)
    obs_tau, obs_mu, state, log_w_f_z, q_eta, p_eta, q_z, p_z, ll = Init_step_eta_test(model_os, obs, N, K, D, sample_size, batch_size)
    w_f_z = F.softmax(log_w_f_z, 0).detach()
    # eubos[0] = (w_f_z * log_w_f_z).sum(0).mean()  ## weights S * B
    ELBOs.append(log_w_f_z.mean().unsqueeze(0))
    LLs.append(ll.unsqueeze(0))
    # esss[0] = (1. / (w_f_z**2).sum(0)).mean()
    for m in range(mcmc_size):
        # if m == 0:
        #     state = resample_state(state, w_f_z, idw_flag=False) ## resample state
        # else:
        #     state = resample_state(state, w_f_z, idw_flag=True)
        q_eta, p_eta, q_nu = enc_eta(obs, state, K, D)
        obs_tau, obs_mu, log_w_eta_f, log_w_eta_b  = Incremental_eta_test(q_eta, p_eta, obs, state, K, D, obs_tau, obs_mu)
        log_w_eta = log_w_eta_f - log_w_eta_b
        DB_eta, eubo_p_q_eta, w_sym_eta, w_f_eta = detailed_balances(log_w_eta_f, log_w_eta_b)
        # obs_mu, obs_tau = resample_eta(obs_mu, obs_tau, w_f_eta, idw_flag=True) ## resample eta
        q_z, p_z = enc_z.forward(obs, obs_tau, obs_mu, N, K, sample_size, batch_size)
        state, log_w_z_f, log_w_z_b, ll = Incremental_z_test(q_z, p_z, obs, obs_tau, obs_mu, K, D, state)
        log_w_z = log_w_z_f - log_w_z_b
        DB_z, eubo_p_q_z, w_sym_z, w_f_z = detailed_balances(log_w_z_f, log_w_z_b)
        ELBOs.append((log_w_eta).mean().unsqueeze(0))
        LLs.append(ll.unsqueeze(0))
        DBs_eta.append(DB_eta.unsqueeze(0))
        DBs_z.append(DB_z.unsqueeze(0))
        # esss[m+1] = ((1. / (w_sym_eta**2).sum(0)).mean() + (1. / (w_sym_z**2).sum(0)).mean() ) / 2
    # reused = (state)
    # metric_step = {"symKL_DB_eta" : symkls_DB_eta, "symKL_DB_z" : symkls_DB_z, "loss" : losss,  "ess" : esss}
    return torch.cat(DBs_eta, 0), torch.cat(DBs_z, 0), torch.cat(ELBOs, 0), torch.cat(LLs, 0)

def ELBO2(models, obs, SubTest_Params):
    """
    Another decomposition of the stepwise elbo
    """
    (device, sample_size, batch_size, N, K, D, mcmc_size) = SubTest_Params
    elbos = []
    joints = []
    ratios = []
    esss = torch.zeros(mcmc_size+1).cuda().to(device)
    (oneshot_eta, enc_eta, enc_z) = models
    model_os = (oneshot_eta, enc_z)
    obs_tau, obs_mu, state, log_p_joint, log_q_ratio, log_p_z = Init_step_eta_test(model_os, obs, N, K, D, sample_size, batch_size)
    # w_f_z = F.softmax(log_w_f_z, 0).detach()
    log_q_ratio_old = 0.0
    joints.append(log_p_joint.mean().unsqueeze(0))
    ratios.append(log_q_ratio.mean().unsqueeze(0))
    elbos.append((log_p_joint + log_q_ratio).mean().unsqueeze(0))
    for m in range(mcmc_size):
        log_q_ratio_old = log_q_ratio_old + log_q_ratio
        q_eta, p_eta, q_nu = enc_eta(obs, state, K, D)
        obs_tau, obs_mu, log_p_joint, log_q_ratio, log_p_eta  = Incremental_eta_test(q_eta, p_eta, obs, state, K, D, obs_tau, obs_mu, log_p_z)
        elbos.append((log_q_ratio_old + log_p_joint + log_q_ratio).mean().unsqueeze(0))
        joints.append(log_p_joint.mean().unsqueeze(0))
        ratios.append(log_q_ratio.mean().unsqueeze(0))

        log_q_ratio_old = log_q_ratio_old + log_q_ratio
        q_z, p_z = enc_z.forward(obs, obs_tau, obs_mu, N, K, sample_size, batch_size)
        state, log_p_joint, log_q_ratio, log_p_z = Incremental_z_test(q_z, p_z, obs, obs_tau, obs_mu, K, D, state, log_p_eta)
        elbos.append((log_q_ratio_old + log_p_joint + log_q_ratio).mean().unsqueeze(0))
        joints.append(log_p_joint.mean().unsqueeze(0))
        ratios.append(log_q_ratio.mean().unsqueeze(0))

    return elbos, joints, ratios
