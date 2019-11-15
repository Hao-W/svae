import sys
sys.path.append('../')
import torch
import time
from utils import shuffler
from baseline_modeling import save_model
from baseline_objective import rws_objective

def train(optimizer, model, architecture, data, K, num_epochs, sample_size, batch_size, CUDA, DEVICE, MODEL_VERSION):
    """
    ==========
    training function of baselines
    ==========
    """
    loss_required = True
    ess_required = True
    mode_required = False
    density_required = True

    num_datasets = data.shape[0]
    N = data.shape[1]
    num_batches = int((num_datasets / batch_size))

    for epoch in range(num_epochs):
        time_start = time.time()
        metrics = dict()
        indices = torch.randperm(num_datasets)
        for b in range(num_batches):
            optimizer.zero_grad()
            batch_indices = indices[b*batch_size : (b+1)*batch_size]
            ob = shuffler(data[batch_indices]).repeat(sample_size, 1, 1, 1)
            if CUDA:
                    ob = ob.cuda().to(DEVICE)
            trace = rws_objective(model=model,
                                       ob=ob,
                                       K=K,
                                       architecture=architecture,
                                       loss_required=loss_required,
                                       ess_required=ess_required,
                                       mode_required=mode_required,
                                       density_required=density_required)

            loss_phi = trace['loss_phi'].sum()
            loss_theta = trace['loss_theta'].sum()
            loss_phi.backward(retain_graph=True)
            loss_theta.backward()
            optimizer.step()
            if loss_required:
                assert trace['loss_phi'].shape == (1, ), 'ERROR! loss_phi has unexpected shape.'
                assert trace['loss_theta'].shape == (1, ), 'ERROR! loss_theta has unexpected shape.'
                if 'loss_phi' in metrics:
                    metrics['loss_phi'] += trace['loss_phi'][-1].item()
                else:
                    metrics['loss_phi'] = trace['loss_phi'][-1].item()
                if 'loss_theta' in metrics:
                    metrics['loss_theta'] += trace['loss_theta'][-1].item()
                else:
                    metrics['loss_theta'] = trace['loss_theta'][-1].item()

            if ess_required:
                assert trace['ess_rws'][0].shape == (batch_size, ), 'ERROR! ess_rws has unexpected shape.'
                if 'ess_rws' in metrics:
                    metrics['ess_rws'] += trace['ess_rws'][0].mean().item()
                else:
                    metrics['ess_rws'] = trace['ess_rws'][0].mean().item()

            if density_required:
                assert trace['density'].shape == (1, batch_size), 'ERROR! density has unexpected shape.'
                if 'density' in metrics:
                    metrics['density'] += trace['density'].mean(-1)[-1].item()
                else:
                    metrics['density'] = trace['density'].mean(-1)[-1].item()
        save_model(model, MODEL_VERSION)
        metrics_print = ",  ".join(['%s: %.6f' % (k, v/num_batches) for k, v in metrics.items()])
        log_file = open('../results/log-' + MODEL_VERSION + '.txt', 'a+')
        time_end = time.time()
        print("(%ds) " % (time_end - time_start) + metrics_print, file=log_file)
        log_file.close()
        print("Epoch=%d completed  in (%ds),  " % (epoch, time_end - time_start))
