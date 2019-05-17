import torch
import time
from utils import *
from normal_gamma import *
from forward_backward import *

def train(models, objective, optimizer, data, Model_Params, Train_Params):
    """
    generic training function
    """
    (NUM_EPOCHS, NUM_DATASETS, S, B, CUDA, device, path) = Train_Params
    SubTrain_Params = (device, S, B) + Model_Params

    NUM_BATCHES = int((NUM_DATASETS / B))
    EPS = torch.FloatTensor([1e-15]).log() ## EPS for KL between categorial distributions
    if CUDA:
        EPS = EPS.cuda().to(device) ## EPS for KL between categorial distributions
    for epoch in range(NUM_EPOCHS):
        metrics = dict()
        time_start = time.time()
        indices = torch.randperm(NUM_DATASETS)
        for step in range(NUM_BATCHES):
            optimizer.zero_grad()
            batch_indices = indices[step*B : (step+1)*B]
            obs = data[batch_indices]
            obs = shuffler(obs).repeat(S, 1, 1, 1)
            if CUDA:
                obs =obs.cuda().to(device)
            loss, metric_step, reused = objective(models, obs, SubTrain_Params)
            ## gradient step
            loss.backward()
            optimizer.step()
            for key in metric_step.keys():
                if key in metrics:
                    metrics[key] += metric_step[key][-1].item()
                else:
                    metrics[key] = metric_step[key][-1].item()
            ## compute KL
            kl_step = kl_train(models, obs, reused, EPS)
            for key in kl_step.keys():
                if key in metrics:
                    metrics[key] += kl_step[key]
                else:
                    metrics[key] = kl_step[key]
        time_end = time.time()
        metrics_print = ",  ".join(['%s: %.3f' % (k, v/NUM_BATCHES) for k, v in metrics.items()])
        flog = open('../results/log-' + path + '.txt', 'a+')
        print(metrics_print, file=flog)
        flog.close()
        print("epoch: %d\\%d (%ds),  " % (epoch, NUM_EPOCHS, time_end - time_start) + metrics_print)

def test_propagation(models, objective, data, Model_Params, Train_Params):
    """
    generic training function
    """
    KLs_propagation = {"kl_eta_ex" : [],"kl_eta_in" : [],"kl_z_ex" : [],"kl_z_in" : []}
    Metrics = {"symKL_DB_eta" : [], "symKL_DB_z" : [], "ess" : []}
    (NUM_DATASETS, S, B, CUDA, device, path) = Train_Params

    NUM_BATCHES = int((NUM_DATASETS / B))
    EPS = torch.FloatTensor([1e-15]).log() ## EPS for KL between categorial distributions
    if CUDA:
        EPS = EPS.cuda().to(device) ## EPS for KL between categorial distributions
    SubTrain_Params = (EPS, device, S, B) + Model_Params
    indices = torch.randperm(NUM_DATASETS)
    time_start = time.time()
    for step in range(NUM_BATCHES):
        batch_indices = indices[step*B : (step+1)*B]
        obs = data[batch_indices]
        obs = shuffler(obs).repeat(S, 1, 1, 1)
        if CUDA:
            obs =obs.cuda().to(device)
        metric_step, reused = objective(models, obs, SubTrain_Params)
        ## gradient step

        for key in Metrics.keys():
            if Metrics[key] == None:
                Metrics[key] = [metric_step[key].cpu().data.numpy()]
            else:
                Metrics[key].append(metric_step[key].cpu().data.numpy())
                
        if step % 100 == 0:
            time_end = time.time()
            print('iteration:%d/%d' % (step, NUM_BATCHES))
            time_start = time.time()
    return Metrics, reused

def test(models, objective, data, Model_Params, Train_Params):
    """
    generic training function
    """
    KLs_propagation = {"kl_eta_ex" : [],"kl_eta_in" : [],"kl_z_ex" : [],"kl_z_in" : []}
    Metrics = {"symKL_DB_eta" : [], "symKL_DB_z" : [], "ess" : []}
    (NUM_DATASETS, S, B, CUDA, device, path) = Train_Params

    NUM_BATCHES = int((NUM_DATASETS / B))
    EPS = torch.FloatTensor([1e-15]).log() ## EPS for KL between categorial distributions
    if CUDA:
        EPS = EPS.cuda().to(device) ## EPS for KL between categorial distributions
    SubTrain_Params = (EPS, device, S, B) + Model_Params
    indices = torch.randperm(NUM_DATASETS)
    time_start = time.time()
    batch_indices = indices[0*B : (0+1)*B]
    obs = data[batch_indices]
    obs = shuffler(obs).repeat(S, 1, 1, 1)
    if CUDA:
        obs =obs.cuda().to(device)
    _, reused = objective(models, obs, SubTrain_Params)
    return obs, reused

def kl_train(models, obs, reused, EPS):
    (oneshot_eta, enc_eta, enc_z) = models
    (state) = reused
    S, B, N, D = obs.shape
    _, _, _, K = state.shape
    q_eta, p_eta, q_nu = enc_eta(obs, state, K, D)
    obs_mu = q_eta['means'].value
    obs_tau = q_eta['precisions'].value
    q_z, p_z = enc_z.forward(obs, obs_tau, obs_mu, N, K, S, B)
    ## KLs for mu and sigma based on Normal-Gamma prior
    q_alpha = q_eta['precisions'].dist.concentration
    q_beta = q_eta['precisions'].dist.rate
    q_mu = q_eta['means'].dist.loc
    q_pi = q_z['zs'].dist.probs
    pr_alpha = p_eta['precisions'].dist.concentration
    pr_beta = p_eta['precisions'].dist.rate
    pr_mu = p_eta['means'].dist.loc
    pr_nu = enc_eta.prior_nu
    pr_pi = p_z['zs'].dist.probs

    post_alpha, post_beta, post_mu, post_nu = Post_eta(obs, state, pr_alpha, pr_beta, pr_mu, pr_nu, K, D)
    kl_eta_ex, kl_eta_in = kls_NGs(q_alpha, q_beta, q_mu, q_nu, post_alpha, post_beta, post_mu, post_nu)
    ## KLs for cluster assignments
    post_logits = Post_z(obs, obs_tau, obs_mu, pr_pi, N, K)
    kl_z_ex, kl_z_in = kls_cats(q_pi.log(), post_logits, EPS)
    kl_step = {"kl_eta_ex" : kl_eta_ex.sum(-1).mean().item(),"kl_eta_in" : kl_eta_in.sum(-1).mean().item(),"kl_z_ex" : kl_z_ex.sum(-1).mean().item(),"kl_z_in" : kl_z_in.sum(-1).mean().item()}
    return kl_step

def EUBO_init_eta_test(models, obs, SubTrain_Params):
    """
    NO Resampling
    Learn neural gibbs samplers for both eta and z,
    non-reparameterized-style gradient estimation
    initialize eta
    """
#     KLs_propagation = {"kl_eta_ex" : [],"kl_eta_in" : [],"kl_z_ex" : [],"kl_z_in" : []}
    
    (EPS, device, sample_size, batch_size, N, K, D, mcmc_size) = SubTrain_Params
    symkls_DB_eta = torch.zeros(mcmc_size).cuda().to(device)
    symkls_DB_z = torch.zeros(mcmc_size).cuda().to(device)
    esss = torch.zeros(mcmc_size+1).cuda().to(device)
    obs_tau, obs_mu, state, log_w_f_z = Init_step_eta(models, obs, N, K, D, sample_size, batch_size, prior_flag=False)
    w_f_z = F.softmax(log_w_f_z, 0).detach()

    (oneshot_eta, enc_eta, enc_z) = models
#         symkls_DB_eta[0] = (w_f_z * log_w_f_z).sum(0).mean() - log_w_f_z.mean()
#         symkls_DB_z[0] = symkls_DB_eta[0] ##
    esss[0] = (1. / (w_f_z**2).sum(0)).mean()
    
#     kl_step = kl_train(models, obs, (state), EPS)
#     for key in KLs_propagation.keys():
#         if KLs_propagation[key] == None:
#             KLs_propagation[key] = [kl_step[key]]
#         else:
#             KLs_propagation[key] = KLs_propagation[key].append(kl_step[key])
        
    for m in range(mcmc_size):
        if m == 0:
            state = resample_state(state, w_f_z, idw_flag=False) ## resample state
        else:
            state = resample_state(state, w_f_z, idw_flag=True)
        q_eta, p_eta, q_nu = enc_eta(obs, state, K, D)
        obs_tau, obs_mu, log_w_eta_f, log_w_eta_b  = Incremental_eta(q_eta, p_eta, obs, state, K, D, obs_tau, obs_mu)
        symkl_detailed_balance_eta, eubo_p_q_eta, w_sym_eta, w_f_eta = detailed_balances(log_w_eta_f, log_w_eta_b, only_forward=True)
        obs_mu, obs_tau = resample_eta(obs_mu, obs_tau, w_f_eta, idw_flag=True) ## resample eta
        q_z, p_z = enc_z.forward(obs, obs_tau, obs_mu, N, K, sample_size, batch_size)
        state, log_w_z_f, log_w_z_b = Incremental_z(q_z, p_z, obs, obs_tau, obs_mu, K, D, state)
        symkl_detailed_balance_z, eubo_p_q_z, w_sym_z, w_f_z = detailed_balances(log_w_z_f, log_w_z_b, only_forward=True)
        ## symmetric KLs as metrics
        symkls_DB_eta[m] = symkl_detailed_balance_eta
        symkls_DB_z[m] = symkl_detailed_balance_z
        esss[m+1] = ((1. / (w_sym_eta**2).sum(0)).mean() + (1. / (w_sym_z**2).sum(0)).mean() ) / 2
        
#         kl_step = kl_train(models, obs, (state), EPS)
#         for key in KLs_propagation.keys():
#             if KLs_propagation[key] == None:
#                 KLs_propagation[key] = [kl_step[key]]
#             else:
#                 KLs_propagation[key] = KLs_propagation[key].append(kl_step[key])
    reused = (q_eta, q_z)
    metric_step = {"symKL_DB_eta" : symkls_DB_eta, "symKL_DB_z" : symkls_DB_z, "ess" : esss}
    return metric_step, reused


def train_baseline(models, objective, optimizer, data, Model_Params, Train_Params):
    """
    generic training function
    """
    (NUM_EPOCHS, NUM_DATASETS, S, B, CUDA, device, path) = Train_Params
    SubTrain_Params = (device, S, B) + Model_Params

    NUM_BATCHES = int((NUM_DATASETS / B))
    EPS = torch.FloatTensor([1e-15]).log() ## EPS for KL between categorial distributions
    if CUDA:
        EPS = EPS.cuda().to(device) ## EPS for KL between categorial distributions
    for epoch in range(NUM_EPOCHS):
        metrics = dict()
        time_start = time.time()
        indices = torch.randperm(NUM_DATASETS)
        for step in range(NUM_BATCHES):
            optimizer.zero_grad()
            batch_indices = indices[step*B : (step+1)*B]
            obs = data[batch_indices]
            obs = shuffler(obs).repeat(S, 1, 1, 1)
            if CUDA:
                obs =obs.cuda().to(device)
            loss, metric_step, reused = objective(models, obs, SubTrain_Params)
            ## gradient step
            loss.backward()
            optimizer.step()
            for key in metric_step.keys():
                if key in metrics:
                    metrics[key] += metric_step[key][-1].item()
                else:
                    metrics[key] = metric_step[key][-1].item()
        time_end = time.time()
        metrics_print = ",  ".join(['%s: %.3f' % (k, v/NUM_BATCHES) for k, v in metrics.items()])
        flog = open('../results/log-' + path + '.txt', 'a+')
        print(metrics_print, file=flog)
        flog.close()
        print("epoch: %d\\%d (%ds),  " % (epoch, NUM_EPOCHS, time_end - time_start) + metrics_print)