import numpy as np
import lmfit
from lmfit.model import Model
import corner

def get_ml_solution(res):
    # find the maximum likelihood solution
    highest_prob = np.argmax(res.lnprob)
    hp_loc = np.unravel_index(highest_prob, res.lnprob.shape)
    mle_soln = res.chain[hp_loc]
    fit_report = "\nMaximum likelihood Estimation"
    fit_report += '\n-----------------------------'
    
    for i, par in enumerate(res.params):
        res.params[par].value = mle_soln[i]
        quantiles = np.percentile(res.flatchain[par], [2.28, 15.9, 50, 84.2, 97.7])
        res.params[par].stderr = 0.5 * (quantiles[3] - quantiles[1])
        fit_report += '\n {} = {} +/- {}'.format(par,res.params[par].value,res.params[par].stderr)

    return res, fit_report

def residual(pars, x, func, data=None, eps=None):
    """2D Residual function to minimize
    """
    model = func.eval(pars, x=x)
    
    if eps is not None:
        resid = (data - model)*eps
    else:
        resid = data - model
    return resid

def lnlike(pars, x, data=None, eps=None):
    v = pars.valuesdict()
    model = v['m'] * x + v['b']
    inv_sigma2 = 1.0/(1/eps**2 + model**2*np.exp(2*np.log(v['f'])))
    return -0.5*(np.sum(residual(pars, x, data)**2*inv_sigma2 - np.log(inv_sigma2/(2*np.pi))))

def init_pars(model,init, x, y):
    pars = model.make_params()
    #make initial guess for parameters
    for vn in pars:
        if vn not in init:
            if model.name == 'Model(linear)':
                if vn == 'm':
                    init[vn] = (np.nanmean(np.diff(y)/np.diff(x)), None, None)
                elif vn == 'b':
                    init[vn] = (y[0], None, None)
            if model.name == 'Model(power)':
                if vn == 'a':
                    init[vn] = (y[0], None, None)
                elif vn == 'n':
                    init[vn] = (1, 0, 6)
                elif vn == 'b':
                    init[vn] = (y[0], None, None)
            if model.name == 'Model(quadratic)':
                if vn == 'a':
                    init[vn] = (np.nanmean(np.diff(y)/np.diff(x)**2), None, None)
                elif vn == 'b':
                    init[vn] = (np.nanmean(np.diff(y)/np.diff(x)), None, None)
                elif vn == 'c':
                    init[vn] = (y[0], None, None)
            if model.name == 'Model(exponential)':
                if vn == 'a':
                    init[vn] = (y[0], None, None)
                elif vn == 't':
                    init[vn] = (x[len(x)//2], 0, None)
                elif vn == 'b':
                    init[vn] = (0, None, None)
        p = init[vn]
        pars[vn].set(p[0], min=p[1], max=p[2])
    return pars

    
#Defined Models: straight line, power law, quadratic, cubic, exponential
def linear(x, m, b):
    return m*x + b

def power(x, a, n, b):
    return a*x**n + b

def quadratic(x, a, b, c):
    return a*x**2 + b*x + c

def exponential(x, a, t, b):
    return a*np.exp(-x/t) + b

# Main Fit Function
def fit_basic( x, y, dy=None, model='line', init={}, fix=None, emcee=False):

    if model in 'linear':
        func = linear
    elif model in 'power':
        func = power
    elif model in 'quadratic':
        func = quadratic
    elif model in 'exponential':
        func = exponential
    else:
        raise ValueError('Model {} not defined.'.format(model))

    model = Model(func, nan_policy='omit')

    pars = init_pars(model, init, x, y)

    if fix is not None:
        for vn in fix:
            pars[vn].set(value=fix[vn], vary=0)

    if dy is not None:
        dy = np.abs(dy)
        wgt = np.array([1./dy[i] if dy[i]>0 else 0 for i in range(len(y))])
    else:
        wgt = None
        
    if emcee:
        mi = lmfit.minimize(residual, pars, args=(x,), kws={'data':y},
                            method='Nelder', nan_policy='omit')
        mi.params.add('f', value=1, min=0.001, max=2)
        mini = lmfit.Minimizer(lnlike, mi.params, fcn_args=(x,), fcn_kws={'data':y, 'eps':wgt})
        out = mini.emcee(burn=300, steps=1000, thin=20, params=mi.params, )
        out, fit_report = get_ml_solution(out)
        print(list(out.params.valuesdict().values()))
        corner.corner(out.flatchain, labels=out.var_names, truths=list(out.params.valuesdict().values()))
        
    else:
        out = lmfit.minimize(residual, pars, args=(x, model), kws={'data':y, 'eps':wgt}, nan_policy='omit')
        fit_report = lmfit.fit_report(out)
        
    pars_arr =  np.zeros((len(pars),2))
    for i,vn in enumerate(pars):
        pars_arr[i,0] = out.params[vn].value
        pars_arr[i,1] = 1.*out.params[vn].stderr

    if not emcee:
        gof = np.array([out.chisqr, out.redchi, out.bic, out.aic])
    else:
        gof = 0
    return pars_arr, gof, out, fit_report, model

