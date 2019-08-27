from matplotlib import pyplot as plt
import numpy as np
from Xana.Xplot.niceplot import niceplot

import matplotlib
import pickle
import pandas as pd
import lmfit
from Xana.Xfit.fit_basic import fit_basic
import ipywidgets as widgets
from ipywidgets import Layout, Button, Box, Text
from IPython.display import display
import qgrid

class ColeCole:

    def __init__(self, d, omega_max=np.inf, gpmax=np.inf):
        self.d = d
        self.omega_max = omega_max
        self.gpmax = gpmax
        self.params = None
        self.pl_data = None
        self.pl_fit = None
        self.dofit = False
        self.fitg0 = False

    @property
    def params(self):
        return self.__params

    @params.setter
    def params(self, p):
        if p is None:
            p = lmfit.Parameters()
            p.add('gosc', value=0, min=0)
            p.add('gmax', value=2, vary=0)

        self.__params = p

    @staticmethod
    def _fit_func(x, gosc):
        return np.sqrt(np.abs(x ** 2 - gosc * x))

    def fit(self, fitg0=False, g0range=[0,200]):

        def residuals(pars, x, data=None ):

            v = pars.valuesdict()
            fit = ColeCole._fit_func(x, v['gosc'])
            resid = (data - fit)
            resid /= data
            return resid

        d = self.d
        omega_max = self.omega_max

        x = 'omega in rad/s'
        y = ["G' in Pa", "G'' in Pa"]

        gp = d[y[0]].values
        gpp = d[y[1]].values
        maxind = np.argmax(gpp[d[x] < self.gpmax])

        gpp_max = gpp[maxind]
        self.params['gosc'].set(2*gpp_max)
        self.params['gmax'].set(gpp_max, vary=0)
        ind = (gp/gpp_max) < omega_max

        out = lmfit.minimize(residuals, self.params, args=(gp[ind],),
                             kws={'data': gpp[ind],}, nan_policy='omit')
        # print(lmfit.fit_report(out))
        self.params = out.params
        self.dofit = True

        if fitg0:
            self.params.add('g0', value=0, vary=0)
            self.params.add('gslp', value=0, vary=0)

            gosc = self.params['gosc'].value
            omega = d[x]
            ind2 = (omega>g0range[0]) & (omega<g0range[1])
            x = gp[ind2]
            y = gpp[ind2]
            # dy = residuals(self.params, x, y)
            p = fit_basic(x, y, model='lin', init={'m':(-gosc/2, None, 0),
                                                   'b':(gosc*2, 0, None)})[2]
            p = p.params
            for k in p:
                err = p[k].stderr
                p[k].stderr = err if err else 0
            self.params['g0'].value = -1. * p['b'].value / p['m'].value
            self.params['g0'].stderr = np.sqrt((p['b'].stderr/p['m'].value)**2
                                               + (p['b'].value*p['m'].stderr/p['m'].value**2)**2)
            self.params['gslp'].value = p['m'].value
            self.params['gslp'].stderr = p['b'].value
            self.fitg0 = True

    def plot(self, ax):

        d = self.d
        # omega_max = self.omega_max

        x = 'omega in rad/s'
        y = ["G' in Pa", "G'' in Pa"]

        ind = d[x] < 90

        gp = d[y[0]].values[ind]
        gpp = d[y[1]].values[ind]
        gpp_max = self.params['gmax'].value

        self.pl_dat, = ax.plot(gp / gpp_max, gpp / gpp_max, 'o')

        ax.set_ylabel("G'' in Pa")
        ax.set_xlabel("G' in Pa")

        if self.dofit:
            textstr = "$G_{{osc}}$ = {:.2g} +/- {:.2g} Pa".format(
                self.params['gosc'].value, self.params['gosc'].stderr)
            xf = np.linspace(0, self.params['gosc'].value, 200)
            yf = ColeCole._fit_func(xf, self.params['gosc'])
            self.pl_fit, = ax.plot(xf / gpp_max, yf / gpp_max, label=textstr, color=self.pl_dat.get_color())
            if self.fitg0:
                xf = np.linspace(gpp_max, 3*gpp_max, 200)
                yf = self.params['gslp'].value * (xf  - self.params['g0'].value)
                textstr = "$G_{{0}}$ = {:.2g} +/- {:.2g} Pa".format(
                    self.params['g0'].value, self.params['g0'].stderr)
                ax.plot(xf / gpp_max, yf / gpp_max, label=textstr, color=self.pl_dat.get_color())
                # ax.legend()
        ax.set_ylim([0, 1.5])
        ax.set_xlim([0, 3])

class Maxwell:

    def __init__(self, d, omega_max=np.inf):
        self.d = d
        self.omega_max = omega_max
        self.params = None
        self.pl_dat = None
        self.pl_fit = None
        self.dofit = False

    @property
    def params(self):
        return self.__params

    @params.setter
    def params(self, p):
        if p is None:
            p = lmfit.Parameters()
            p.add('eta', value=1, min=0)
            p.add('lmbd', value=10, min=0)
            p.add('gp', value=0.1, expr='eta/lmbd')
        self.__params = p

    @staticmethod
    def _mw_gp(x, eta, lbd):
        return (eta * lbd * x ** 2) / (1 + x ** 2 * lbd ** 2)

    @staticmethod
    def _mw_gpp(x, eta, lbd):
        return (eta * x) / (1 + x ** 2 * lbd ** 2)

    def fit(self):

        def residuals(pars, x, gp, gpp):
            """2D Residual function to minimize
            """
            v = pars.valuesdict()
            resid = np.zeros((2, gp.size))
            resid[0] = (gp - Maxwell._mw_gp(x, v['eta'], v['lmbd']))
            resid[1] = (gpp - Maxwell._mw_gpp(x, v['eta'], v['lmbd']))
            return np.squeeze(resid.flatten())

        d = self.d
        xn = 'omega in rad/s'
        yn = ["G' in Pa", "G'' in Pa"]
        omega = d[xn]
        gp = d[yn[0]]
        gpp = d[yn[1]]
        indf = omega < self.omega_max
        omega = omega[indf]
        gp = gp[indf]
        gpp = gpp[indf]

        out = lmfit.minimize(residuals, self.params,
                             args=(omega, gp, gpp),
                             nan_policy='omit')

        self.params = out.params
        self.dofit = True

    def plot(self, ax, cc_cutoff=False):

        d = self.d
        fill_style = {0: 'none', 1: 'full'}

        xn = 'omega in rad/s'
        yn = ["G' in Pa", "G'' in Pa"]
        fc = 0
        color = None
        for yni in yn:
            x = d[xn].values
            y = d[yni].values
            pl, = ax.plot(x, y, 'o-', fillstyle=fill_style[fc], color=color)
            if fc == 0:
                color = pl.get_color()
                fc = 1

        ax.set_xlabel(xn)
        ax.set_ylabel("G', G'' in Pa")

        ax.set_xscale('log')
        ax.set_yscale('log')

        # if cc_cutoff:
        #     lim = ax.get_ylim()
        #     ax.vlines(cc_cutoff, lim[0], lim[1], color=pl.get_color(), linestyles='dashed')

        if self.dofit:
            xf = np.logspace(0, 2, 200)
            p = self.params
            gpf = Maxwell._mw_gp(xf, p['eta'].value, p['lmbd'].value)
            gppf = Maxwell._mw_gpp(xf, p['eta'].value, p['lmbd'].value)
            ax.plot(xf, gpf, '-', color=pl.get_color())
            ax.plot(xf, gppf, '-', color=pl.get_color())


class Rheo:
    """Base class to analyze rheology data.
    """

    def __init__(self, df, datdir='./data'):

        self.df = df
        self.datdir = datdir
        self.register = {
            'all': None,
            'dynamic_moduli': 1,
            'flow_curve': 2,
        }
        self.plots = {
            'dynamic moduli': 1,
            'dynamic viscosity': 0,
            'cole-cole': 1,
            'flow curve eta': 1,
            'flow curve tau': 0,
            'temperature': 0,
        }
        self.nplots = sum([x for x in self.plots.values()])
        self.ax = None
        self.fig = None
        self.params = None
        self.table = None
        self.interactive = False

    @staticmethod
    def read_rheo_data(filename):
        return pd.read_csv(filename, sep=';', na_values=' ')

    def dname(self, row, counter=None, ):
        fname = row['file'].replace('.rwd', '').replace('.csv','')
        if counter:
            fname = row['datdir'] +'/'+ fname + '_{:02d}.dat'.format(counter)
        else:
            fname = row['datdir'] +'/'+ fname + '.dat'
        return fname

    @staticmethod
    def plot_dynamic_viscosity(d, ax):
        x = 'omega in rad/s'
        y = '|Eta*| in Pas'
        pl, = ax.plot(d[x].values, d[y].values, marker='o', )
        ax.set_xscale('log')
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        return pl

    @staticmethod
    def plot_flow_curve_tau(d, ax):
        x = 'GP in 1/s'
        y = 'Tau in Pa'
        ax.plot(d[x].values, d[y].values, marker='o', )
        ax.set_xlabel(x)
        ax.set_ylabel(y)

    @staticmethod
    def plot_flow_curve_eta(d, ax, rngx=(0.02, 0.2), rngy=(0,100)):
        xn = 'GP in 1/s'
        yn = 'Eta in Pas'
        x = d[xn].values
        y = d[yn].values
        ind = x > 0.01
        x = x[ind]
        y = y[ind]
        ind = (x > rngx[0]) & (x < rngx[1]) & (y > rngy[0]) & (y < rngy[1])
        eta = np.mean(y[ind])
        deta = np.std(y[ind])

        ax.plot(x, y, marker='o', label=r'$\eta_0$ = {:.2f} +/- {:.2f} Pas'.format(eta, deta))
        ax.set_xlabel(xn)
        ax.set_ylabel(yn)
        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.vlines(rngx[0], eta - deta * 5, eta + deta * 5)
        ax.vlines(rngx[1], eta - deta * 5, eta + deta * 5)
        ax.legend()
        return eta, deta

    @staticmethod
    def plot_viscosity_aging(d, ax):
        x = 't_seg in s'
        y = '|Eta*| in Pas'
        ax.plot(d[x].values, d[y].values, marker='o', )
        ax.set_xlabel(x)
        ax.set_ylabel(y)

    @staticmethod
    def plot_temperature(d, ax):
        x = 't in s'
        y = 'T in °C'
        ax.plot(d[x].values, d[y].values, marker='o', )
        ax.set_xlabel(x)
        ax.set_ylabel(y)

    def init_figure(self, ):

        nplots = sum([int(x) for x in self.plots.values()])
        if nplots != self.nplots:
            self.nplots = nplots
            if self.fig is not None:
                self.fig.clf()
            self.ax = None

        if self.ax is None:
            ncols = 1 if self.nplots <= 1 else 2
            nrows = (self.nplots + 1) // 2
            self.fig, ax = plt.subplots(nrows, ncols, figsize=(ncols * 4, nrows * 3))
            self.ax = ax.flatten() if isinstance(ax, np.ndarray) else [ax, ]
        else:
            for axi in self.ax:
                axi.clear()

    def add_columns(self, columns):
        for c in columns[::-1]:
            if not c in self.df.columns:
                self.df.insert(7, c, np.nan)
            if self.table is not None:
                if not c in self.table.df.columns:
                    self.table.df.insert(7, c, np.nan)

    @staticmethod
    def set_rowparams(row, params):
        for p in params:
            row[f'{p}'] = params[p].value
            row[f'd_{p}'] = params[p].stderr

    def plot(self, df=None, dofit=True, cole_omega_max=30, maxwell_omega_max=40, g0range=[0,200], fitg0=False,
             defaultQ=1, gpmax=np.inf):

        if df is None:
            df = self.df

        ax = self.ax
        h_plot = []
        for index, row in df[df['plot']].iterrows():

            if '18' in row['datdir']:
                register = {
                    'all': None,
                    'dynamic_moduli': 2,
                    'flow_curve': 3,
                }
            elif 'data' in row['datdir':
                register = {
                    'all': None,
                    'dynamic_moduli': 1,
                    'flow_curve': 2,
                }
            elif 'p6380' in row['datdir']:
                register = {
                    'all': None,
                    'dynamic_moduli': 1,
                    'flow_curve': 2,
                }
            else:
                continue

            ax_index = 0
            row['quality'] = defaultQ
            for pn, pv in self.plots.items():

                if pn == 'dynamic moduli' and pv:
                    d = self.read_rheo_data(self.dname(row, register['dynamic_moduli']))
                    mw = Maxwell(d, maxwell_omega_max)
                    if dofit:
                        mw.fit()
                        self.set_rowparams(row, mw.params)
                    mw.plot(ax[ax_index], cole_omega_max)
                    ax_index += 1

                if pn == 'cole-cole' and pv:
                    d = self.read_rheo_data(self.dname(row, register['dynamic_moduli']))
                    cc = ColeCole(d, cole_omega_max, gpmax)
                    if dofit:
                        cc.fit(fitg0, g0range)
                        self.set_rowparams(row, cc.params)
                    cc.plot(ax[ax_index])
                    h_plot.append((index, cc.pl_dat))
                    ax_index += 1

                if pn == 'dynamic viscosity' and pv:
                    d = self.read_rheo_data(self.dname(row, register['dynamic_moduli']))
                    self.plot_dynamic_viscosity(d, ax[ax_index])
                    ax_index += 1

                if pn == 'temperature' and pv:
                    d = self.read_rheo_data(self.dname(row, register['all']))
                    self.plot_temperature(d, ax[ax_index])
                    ax_index += 1

                if pn == 'flow curve eta' and pv:
                    d = self.read_rheo_data(self.dname(row, register['flow_curve']))
                    rng = [x.value for x in self.fc_box.children]
                    eta, deta = self.plot_flow_curve_eta(d, ax[ax_index], rng[:2], rng[2:])
                    row['eta0'] = eta
                    row['d_eta0'] = deta
                    ax_index += 1

                if pn == 'flow curve tau' and pv:
                    d = self.read_rheo_data(self.dname(row, register['flow_curve']))
                    self.plot_flow_curve_tau(d, ax[ax_index])
                    ax_index += 1

            self.add_columns(row.index)
            df.loc[index] = row
            # self.table.df.loc[index] = row


        if self.interactive:
            legstr = [str(x[0]) for x in h_plot]
            h = [x[1] for x in h_plot]
            ax[0].legend(h, legstr, bbox_to_anchor=(0, 1.02, 1, 0.2), loc="lower left",
            mode="expand", borderaxespad=0, ncol=len(legstr))
            plt.tight_layout()
            plt.show()
            self.table.df = df

    def interact(self, ):

        def update_plot(*args):
            for b in togPlot:
                self.plots[b.description] = b.value
            self.init_figure()
            self.plot(self.table.get_changed_df(),
                           dofit=tb_plotfit.value,
                           cole_omega_max=ft_cc.value,
                           maxwell_omega_max=ft_mw.value,
                           g0range=frs_g0fit.value,
                           fitg0=tb_fitg0.value,
                           defaultQ=ft_quality.value,
                           gpmax=ft_gpmax.value
                           )
            # self.df = df

        def write_df(*args):
            df = self.table.get_changed_df()
            self.df.update(df)
            # self.table.df = self.df
            self.df['plot'] = False

        def save(*args):
            write_df()
            pickle.dump(self.df, open(t_save.value, 'wb'))

        def reset_plot(*args):
            df = self.table.get_changed_df()
            df['plot'] = False
            self.table.df = df

        def update_table(*args):
            self.table.df.update(self.table.get_changed_df())

        self.interactive = True

        self.table = qgrid.show_grid(self.df,
                                       grid_options={
                                        'forceFitColumns': False,
                                        'defaultColumnWidth': 70,
                                       })

        box_layout = Layout(overflow_x='scroll',
                            flex_flow='row',
                            display='flex')
        btable = Box(children=[self.table], layout=box_layout)

        w = widgets.SelectMultiple(
            options=self.table.get_changed_df()['file'],
            value=[],
            # rows=10,
            description='Rheo Data Sets',
            disabled=False,
            layout=widgets.Layout(width='40%', height='160px'),
            style={'description_width': 'initial'}
        )

        items_layout = Layout(flex='1 1 auto', width='auto')

        box_layout = Layout(display='flex',
                            flex_flow='row',
                            width='75%')

        togPlot = [widgets.ToggleButton(description=word,
                                        value=bool(value),
                                        layout=items_layout,
                                        button_style='info')
                   for word, value in self.plots.items()
                   ]

        plotl = Box(children=togPlot, layout=box_layout)

        b_plot = widgets.Button(
            description='plot',
            button_style='info',  # 'success', 'info', 'warning', 'danger' or ''
        )
        b_plot.on_click(update_plot)

        tb_plotfit = widgets.ToggleButton(
            description='plot fit',
            value=True,
            button_style='info'
        )

        b_wpars = widgets.Button(
            description='write fit params',
            button_style='info',
        )
        b_wpars.on_click(write_df)

        t_save = widgets.Text(value='RheoAnalysis.pkl',
                              disabled=False
                              )
        ft_quality = widgets.FloatText(
                        value=1,
                        min=0,
                        max=1,
                        step=0.2,
                        description='Quality:',
                        disabled=False,
                        layout=Layout(width='15%')
                    )

        b_save = widgets.Button(
            description='save',
            button_style='info',
        )
        b_save.on_click(save)

        b_resetplot = widgets.Button(
            description='reset plot',
            button_style='info',
        )
        b_resetplot.on_click(reset_plot)

        b_updatetable = widgets.Button(
            description='update',
            button_style='info',
        )
        b_updatetable.on_click(update_table)

        # Widgets Maxwell Plot
        ft_mw = widgets.FloatText(
            value=6,
            description=r'MW: $\omega_{max}$',
            disabled=False,
            layout=Layout(width='15%')
        )

        # Widgets Cole-Cole Plot
        ft_cc = widgets.FloatText(
            value=1.5,
            description=r'Cole-Cole: $G_p/G_{max}$',
            disabled=False,
            layout=Layout(width='15%')
        )
        ft_gpmax = widgets.FloatText(
            value=90,
            description=r'$\omega_{max}$ for plot',
            disabled=False,
            layout=Layout(width='15%')
        )

        tb_fitg0 = widgets.ToggleButton(
            description=r'fit $G_0$',
            value=False,
            button_style='info'
        )

        frs_g0fit = widgets.FloatRangeSlider(
            value=[6, 24],
            min=1,
            max=150,
            step=1,
            description=r'$\omega$ range:',
            disabled=False,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.0f',
        )

        # Widgets Flow Curve
        fls_fc_gpmin = widgets.FloatLogSlider(
            value=0.02,
            base=10,
            min=-2,  # max exponent of base
            max=1,  # min exponent of base
            step=0.2,  # exponent step
            description=r'FC: GP min'
        )
        fls_fc_gpmax = widgets.FloatLogSlider(
            value=0.2,
            base=10,
            min=-2,  # max exponent of base
            max=1,  # min exponent of base
            step=0.2,  # exponent step
            description='GP max'
        )
        fls_fc_etamin = widgets.FloatLogSlider(
            value=1e-3,
            base=10,
            min=-3,  # max exponent of base
            max=1,  # min exponent of base
            step=0.2,  # exponent step
            description=r'FC: eta min'
        )
        fls_fc_etamax = widgets.FloatLogSlider(
            value=100,
            base=10,
            min=-2,  # max exponent of base
            max=2,  # min exponent of base
            step=0.2,  # exponent step
            description='eta max'
        )
        self.cc_box = widgets.HBox([ft_cc, frs_g0fit, tb_fitg0, ft_gpmax])
        self.mw_box = widgets.HBox([ft_mw, ft_quality])
        self.fc_box = widgets.HBox([fls_fc_gpmin, fls_fc_gpmax, fls_fc_etamin, fls_fc_etamax])

        # output = widgets.Output()

        # display(output)
        # with output:
        display(btable)
        gui = widgets.VBox([widgets.HBox([b_plot, t_save, b_save, b_resetplot, tb_plotfit, b_wpars,]),
                            plotl, self.mw_box, self.cc_box, self.fc_box] )
        display(gui)

