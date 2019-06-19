 import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions.normal import Normal
import probtorch
import math

class Dec_x(nn.Module):
    def __init__(self, D, num_hidden, CUDA, device):
        super(self.__class__, self).__init__()
        self.x_mu = nn.Sequential(
            nn.Linear(1+1, num_hidden),
            nn.Tanh(),
            nn.Linear(num_hidden, D))
        self.x_log_sigma  = nn.Sequential(
            nn.Linear(1+1, num_hidden),
            nn.Tanh(),
            nn.Linear(num_hidden, D))

    def forward(self, obs, state, obs_mu, obs_rad):
        p = probtorch.Trace()
        S, B, N, D = obs.shape
        labels = state.argmax(-1)
        labels_mu = labels.unsqueeze(-1).repeat(1, 1, 1, D)
        obs_mu_expand = torch.gather(obs_mu, 2, labels_mu)
        distances = ((obs - obs_mu_expand) ** 2).sum(-1).sqrt().unsqueeze(-1) ## S * B * N * 1
        vars = torch.cat((distances, obs_rad.repeat(S, B, N, 1)), -1)
        x_mu = self.x_mu(vars)
        x_sigma = self.x_log_sigma(vars).exp()
        x_recon = Normal(x_mu, x_sigma).sample()
        p.normal(x_mu,
                 x_sigma,
                 value=x_recon,
                 name='x_recon')

        return p
