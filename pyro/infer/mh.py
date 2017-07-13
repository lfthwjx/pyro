import torch
from torch.autograd import Variable

import pyro
import pyro.poutine as poutine
from pyro.distributions import Uniform, Categorical


class MH(pyro.infer.abstract_infer.AbstractInfer):
    """
    Initial implementation of MH MCMC
    """
    def __init__(self, model, guide=None, proposal=None, samples=10, lag=1, burn=0):
        super(MH, self).__init__()
        self.samples = samples
        self.lag = lag
        self.burn = burn
        self.model = model
        assert (guide is None or proposal is None) and \
            (guide is not None or proposal is not None), \
            "cannot have guide and proposal"
        if guide is not None:
            self.guide = lambda tr, *args, **kwargs: guide(*args, **kwargs)
        else:
            self.guide = proposal

    def _traces(self, *args, **kwargs):
        """
        make trace posterior distribution
        """
        # initialize traces with a draw from the prior
        old_model_trace = poutine.trace(self.model)(*args, **kwargs)
        traces = []
        t = 0
        while t < self.burn + self.lag * self.samples:
            # p(x, z)
            old_model_trace = traces[-1]
            # q(z' | z)
            new_guide_trace = poutine.block(
                poutine.trace(self.guide))(old_model_trace, *args, **kwargs)
            # p(x, z')
            new_model_trace = poutine.trace(
                poutine.replay(self.model, new_guide_trace))(*args, **kwargs)
            # q(z | z')
            old_guide_trace = poutine.block(
                poutine.trace(
                    poutine.replay(self.guide, new_model_trace)))(new_model_trace,
                                                                  *args, **kwargs)
            # p(x, z') q(z' | z) / p(x, z) q(z | z')
            logr = new_model_trace.log_pdf() + new_guide_trace.log_pdf() - \
                   old_model_trace.log_pdf() + old_guide_trace.log_pdf()
            rnd = pyro.sample("mh_step_{}".format(i),
                              Uniform(pyro.zeros(1), pyro.ones(1)))
            if torch.log(rnd)[0] < logr[0]:
                # accept
                old_model_trace = new_model_trace
                if t <= self.burn or (t > self.burn and t % self.lag == 0):
                    t += 1
                    traces.append(new_model_trace)

        log_weights = [tr.log_pdf() for tr in traces]
        return traces, log_weights


##############################################
# Non-functioning MH subclasses and helpers
##############################################
# 
# def hmc_proposal(model, sites=None):
#     def _fn(tr, *args, **kwargs):
#         for i in range(steps):
#             tr = poutine.block(poutine.trace(poutine.replay(model, tr, sites=sites)))(*args, **kwargs)
#             logp = tr.log_pdf()
#             samples = values(tr.filter(site_type="sample"))
#             autograd.backward(samples, logp)
#             optimizer.step(samples)
#         return tr
#     return _fn
# 
# 
# def single_site_proposal(model):
#     def _fn(tr, *args, **kwargs):
#         name = itertools.randomchoice(tr.filter(site_type="sample").keys())
#         new_site = propose(tr[name])
#         new_tr = tr.copy()
#         new_tr[name] = new_site
#         new_tr = poutine.trace(
#             poutine.replay(model, new_tr, sites=parents(tr, name)))(*args, **kwargs)
#         return new_tr
#     return _fn
# 
# 
# def mixture_guide(guides):
#     return lambda *args, **kwargs: guides[pyro.sample(gensym(), discrete, guides, ones())](*args, **kwargs)
# 
# 
# class MixedHMCMH(MH):
#     def __init__(self, model):
#         proposal = mixture_guide([hmc_proposal(model),
#                                   single_site_proposal(model)])
#         super(MixedHMCMH, self).__init__(model, proposal=proposal)
# 
# 
# class HMC(MH):
#     def __init__(self, model):
#         super(HMC, self).__init__(model, proposal=hmc_guide(model))
# 
# 
# class SingleSiteMH(MH):
#     def __init__(self, model):
#         super(SingleSiteMH, self).__init__(model, proposal=single_site_guide(model))
