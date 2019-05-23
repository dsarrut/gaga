import numpy as np
import torch
from torch.autograd import Variable
import gaga
import datetime
import os
import phsp
from scipy.stats import kde
from matplotlib import pyplot as plt
import seaborn as sns
from scipy.stats import entropy

''' ---------------------------------------------------------------------------------- '''
'''
date format
'''
date_format = "%Y-%m-%d %H:%M:%S"


''' ---------------------------------------------------------------------------------- '''
def init_pytorch_cuda(gpu_mode, verbose=False):
    '''
    Test if pytorch use CUDA. Return type and device
    '''
    
    if (verbose):
        print('pytorch version', torch.__version__)
    dtypef = torch.FloatTensor
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    if (gpu_mode == 'auto'):
        if (torch.cuda.is_available()):
            dtypef = torch.cuda.FloatTensor
    elif (gpu_mode == 'true'):
        if (torch.cuda.is_available()):
            dtypef = torch.cuda.FloatTensor
        else:
            print('Error GPU mode not available')
            exit(0)
    else:
        device = torch.device('cpu');

    if (verbose):
        if (str(device) != 'cpu'):
            print('GPU is enabled')
            # print('CUDA version: ', torch.version.cuda)
            # print('CUDA device name:', torch.cuda.get_device_name(0))
            # print('CUDA current device: ', torch.cuda.current_device())
            # print('CUDA device:', torch.cuda.device(0))
            # print('CUDA device counts: ', torch.cuda.device_count())
        else:
            print('CPU only (no GPU)')

    return dtypef, device



''' ---------------------------------------------------------------------------------- '''
def print_network(net):
    '''
    Print info about a network
    '''

    num_params = get_network_nb_parameters(net)
    print(net)
    print('Total number of parameters: %d' % num_params)


''' ---------------------------------------------------------------------------------- '''
def get_network_nb_parameters(net):
    '''
    Compute total nb of parameters
    '''
    num_params = 0
    for param in net.parameters():
        num_params += param.numel()
    return num_params


''' ---------------------------------------------------------------------------------- '''
def print_info(params, optim):
    '''
    Print info about a trained GAN-PHSP
    '''
    # print parameters
    for e in params:
        if (e[0] != '#') and (e != 'x_mean') and (e != 'x_std'):
            print('   {:20s} {}'.format(e, str(params[e])))

    # additional info
    try:
        start = datetime.datetime.strptime(params['start date'], gaga.date_format)
        end = datetime.datetime.strptime(params['end date'], gaga.date_format)
    except:
        start = 0
        end = 0
    delta = end-start
    print('   {:20s} {}'.format('Duration', delta))

    d_loss_real = np.asarray(optim['d_loss_real'][-1])
    d_loss_fake = np.asarray(optim['d_loss_fake'][-1])
    d_loss = d_loss_real + d_loss_fake
    g_loss = np.asarray(optim['g_loss'][-1])
    print('   {:20s} {}'.format('Final d_loss', d_loss))
    print('   {:20s} {}'.format('Final g_loss', g_loss))


''' ---------------------------------------------------------------------------------- '''
def load(filename, verbose=False):
    '''
    Load a GAN-PHSP
    Output params   = dict with all parameters
    Output G        = Generator network
    Output optim    = dict with information of the training process
    '''
    
    dtypef, device = init_pytorch_cuda('auto', verbose)
    if (str(device) == 'cpu'):
        nn = torch.load(filename, map_location=lambda storage, loc: storage)
    else:
        nn = torch.load(filename)

    # get elements
    params = nn['params']
    if not 'optim' in nn:
        optim = nn['model'] ## FIXME compatibility --> to remove
    else:
        optim =  nn['optim']
    G_state = nn['g_model_state']

    # create the Generator
    cmin, cmax = gaga.get_min_max_constraints(params)
    cmin = torch.from_numpy(cmin).type(dtypef)
    cmax = torch.from_numpy(cmax).type(dtypef)
    G = gaga.Generator(params, cmin, cmax)
    
    if (str(device) != 'cpu'):
        G.cuda()
        params['current_gpu'] = True
    else:
        params['current_gpu'] = False

    G.load_state_dict(G_state)

    return params, G, optim, dtypef

''' ---------------------------------------------------------------------------------- '''
def get_min_max_constraints(params):
    '''
    Compute the min/max values per dimension according to params['keys'] and params['constraints']
    '''
    
    # clamp take normalisation into account
    x_dim = params['x_dim']
    keys = params['keys']
    ckeys = params['constraints']
    cmin = np.ones((1, x_dim)) * -9999 # FIXME min value
    cmax = np.ones((1, x_dim)) *  9999 # FIXME max value
    for k,v in ckeys.items():
        try:
            index = keys.index(k)
            cmin[0,index] = v[0]
            cmax[0,index] = v[1]
        except:
            continue
        
    x_std = params['x_std']
    x_mean = params['x_mean']
    
    #print(cmin, cmax)
    cmin = (cmin-x_mean)/x_std
    cmax = (cmax-x_mean)/x_std
    #print(cmin, cmax)

    return cmin, cmax
    

''' ---------------------------------------------------------------------------------- '''
def plot_epoch(ax, optim, filename):
    '''
    Plot D loss wrt to epoch
    3 panels : all epoch / first 20% / last 1% 
    '''

    x1 = np.asarray(optim['d_loss_real'])
    x2 = np.asarray(optim['d_loss_fake'])
    x = -np.add(x1,x2)

    a = ax[0]
    l = filename
    a.plot(x, '-', label='D_loss '+l)
    z = np.zeros_like(x)
    a.set_xlabel('epoch')
    a.plot(z, '--')
    a.legend()

    a = ax[1]
    n = int(len(x)*0.2) # first 20%
    xc = x[0:n]
    a.plot(xc, '-', label='D_loss '+l)
    z = np.zeros_like(xc)
    a.set_xlabel('epoch')
    a.set_xlim((0,n))
    ymin = np.amin(xc)
    ymax = np.amax(xc)
    a.set_ylim((ymin,ymax))
    a.plot(z, '--')
    a.legend()
    
    a = ax[2]
    n = max(10, int(len(x)*0.01)) # last 1%
    xc = x
    a.plot(xc, '.-', label='D_loss '+l)
    z = np.zeros_like(xc)
    a.set_xlabel('epoch')
    a.set_xlim((len(xc)-n,len(xc)))
    xc = x[len(x)-n:len(x)]
    ymin = np.amin(xc)
    ymax = np.amax(xc)
    a.set_ylim((ymin,ymax))
    a.plot(z, '--')
    a.legend()

    
''' ---------------------------------------------------------------------------------- '''
def generate_samples(params, G, dtypef, n):

    z_dim = params['z_dim']
    x_mean = params['x_mean']
    x_std = params['x_std']
    z = Variable(torch.randn(n, z_dim)).type(dtypef)
    fake = G(z)
    fake = fake.cpu().data.numpy()
    fake = (fake*x_std)+x_mean

    return fake


''' ---------------------------------------------------------------------------------- '''
def generate_samples_torch(params, G, dtypef, n):

    z_dim = params['z_dim']
    x_mean = params['x_mean']
    x_std = params['x_std']
    z = Variable(torch.randn(n, z_dim)).type(dtypef)
    fake = G(z)

    x_mean = Variable(torch.from_numpy(x_mean)).type(dtypef)
    x_std = Variable(torch.from_numpy(x_std)).type(dtypef)
    #fake = fake.cpu().data.numpy()
    fake = (fake*x_std)+x_mean

    return fake


''' ---------------------------------------------------------------------------------- '''
def generate_samples2(params, G, n, batch_size=-1, un_norm=True, to_numpy=False):

    z_dim = params['z_dim']

    if params['current_gpu']:
        dtypef = torch.cuda.FloatTensor
    else:
        dtypef = torch.FloatTensor
        
    z_dim = params['z_dim']

    batch_size = int(batch_size)
    if batch_size == -1:
        batch_size = n
        to_numpy = True
    if batch_size>n:
        batch_size = n

    m = 0
    rfake = np.empty((0,params['x_dim']))
    while m < n:
        z = Variable(torch.randn(batch_size, z_dim)).type(dtypef)
        fake = G(z)
        if un_norm:
            x_mean = params['x_mean']
            x_std = params['x_std']
            x_mean = Variable(torch.from_numpy(x_mean)).type(dtypef)
            x_std = Variable(torch.from_numpy(x_std)).type(dtypef)
            fake = (fake*x_std)+x_mean
        if to_numpy:
            fake = fake.cpu().data.numpy()
            rfake = np.concatenate((rfake, fake), axis=0)
        m = m+batch_size
        if m+batch_size>n:
            batch_size = n-m

    if to_numpy == False:
        return fake
    return rfake


''' ---------------------------------------------------------------------------------- '''
def fig_plot_marginal(x, k, keys, ax, i, nb_bins, color):
    a = phsp.fig_get_sub_fig(ax,i)
    index = keys.index(k)
    if len(x[0])>1:
        d = x[:,index]
    else:
        d = x
    label = ' {} $\mu$={:.2f} $\sigma$={:.2f}'.format(k, np.mean(d), np.std(d))
    a.hist(d, nb_bins,
           # density=True,
           histtype='stepfilled',
           facecolor=color,
           alpha=0.5,
           label=label)
    a.set_ylabel('Counts')
    a.legend()


''' ---------------------------------------------------------------------------------- '''
def fig_plot_marginal_2d(x, k1, k2, keys, ax, i, nbins, color):
    a = phsp.fig_get_sub_fig(ax,i)
    index1 = keys.index(k1)
    d1 = x[:,index1]
    index2 = keys.index(k2)
    d2 = x[:,index2]
    label = '{} {}'.format(k1, k2)

    ptype = 'scatter'
    # ptype = 'density'
    
    if ptype == 'scatter':
        a.scatter(d1, d2, color=color,
                  alpha=0.25,
                  edgecolor='none',
                  s=1)        
        
    if ptype == 'hist':
        cmap = plt.cm.Greens
        if color == 'r':
            cmap = plt.cm.Reds
        a.hist2d(d1, d2,
                 bins=(nbins, nbins), 
                 alpha=0.5,
                 cmap=cmap)

    if ptype == 'density':
        x = d1
        y = d2
        print('kde')
        k = kde.gaussian_kde([x,y])
        xi, yi = np.mgrid[x.min():x.max():nbins*1j, y.min():y.max():nbins*1j]
        zi = k(np.vstack([xi.flatten(), yi.flatten()]))
        a.pcolormesh(xi, yi,
                     zi.reshape(xi.shape), 
                     alpha=0.5)

        
        
    a.set_xlabel(k1)
    a.set_ylabel(k2)

    

''' ---------------------------------------------------------------------------------- '''
def Jensen_Shannon_divergence(x, y, bins, margin=0):

    #margin = 0#.01 # 5%
    r = [np.amin(x), np.amax(x)]
    if r[0]<0:
        r = [r[0]+margin*r[0], r[1]+margin*r[1]]
    else:
        r = [r[0]-margin*r[0], r[1]+margin*r[1]]
    P, bin_edges = np.histogram(x, range=r, bins=bins, density=True)
    Q, bin_edges = np.histogram(y, range=r, bins=bins, density=True)
    
    _P = P / np.linalg.norm(P, ord=1)
    _Q = Q / np.linalg.norm(Q, ord=1)
    _M = 0.5 * (_P + _Q)
    return 0.5 * (entropy(_P, _M) + entropy(_Q, _M))



''' ---------------------------------------------------------------------------------- '''
def sliced_wasserstein(x, y, l, p=2):
    l = int(l)
    ndim = len(x[0])

    # directions: matrix [ndim X l]
    directions = np.random.randn(ndim, l)
    directions /= np.linalg.norm(directions, axis=0)

    # send to gpu if possible
    dtypef = torch.FloatTensor
    if x.is_cuda:
        dtypef = torch.cuda.FloatTensor
    directions = torch.from_numpy(directions).type(dtypef)

    # Projection (Radon) x = [n X ndim], px = [n X L]
    px = torch.matmul(x,directions)
    py = torch.matmul(y,directions)

    # sum wasserstein1D over all directions
    d = 0
    for i in range(l):
        lx = px[:,i]
        ly = py[:,i]
        d += wasserstein1D(lx, ly, p)
    d = d/l
    
    d = d.data.cpu().numpy()
    return d

''' ---------------------------------------------------------------------------------- '''
def wasserstein1D(x, y, p=2):
    sx, indices = torch.sort(x)
    sy, indices = torch.sort(y)
    z = (sx-sy)
    return torch.sum(torch.pow(torch.abs(z), p))/len(z)

