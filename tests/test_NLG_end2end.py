# available NLU models
# from convlab2.nlu.svm.multiwoz import SVMNLU
from logging import raiseExceptions
from re import U
from convlab2.nlu.jointBERT.multiwoz import BERTNLU
# from convlab2.nlu.milu.multiwoz import MILU
# available DST models
from convlab2.dst.rule.multiwoz import RuleDST
# from convlab2.dst.mdbt.multiwoz import MDBT
# from convlab2.dst.sumbt.multiwoz import SUMBT
# from convlab2.dst.trade.multiwoz import TRADE
# from convlab2.dst.comer.multiwoz import COMER
# available Policy models
from convlab2.policy.rule.multiwoz import RulePolicy
# from convlab2.policy.ppo.multiwoz import PPOPolicy
# from convlab2.policy.pg.multiwoz import PGPolicy
# from convlab2.policy.mle.multiwoz import MLEPolicy
# from convlab2.policy.gdpl.multiwoz import GDPLPolicy
# from convlab2.policy.vhus.multiwoz import UserPolicyVHUS
# from convlab2.policy.mdrg.multiwoz import MDRGWordPolicy
# from convlab2.policy.hdsa.multiwoz import HDSA
# from convlab2.policy.larl.multiwoz import LaRL
# available NLG models
from convlab2.nlg.template.multiwoz import TemplateNLG
from convlab2.nlg.sclstm.multiwoz import SCLSTM
from convlab2.nlg.scgpt.multiwoz import SCGPT, scgpt
# available E2E models
# from convlab2.e2e.sequicity.multiwoz import Sequicity
# from convlab2.e2e.damd.multiwoz import Damd
from convlab2.dialog_agent import PipelineAgent, BiSession
from convlab2.evaluator.multiwoz_eval import MultiWozEvaluator
from convlab2.util.analysis_tool.analyzer import Analyzer
from pprint import pprint
import random
import numpy as np
import torch
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser



def set_seed(r_seed):
    random.seed(r_seed)
    np.random.seed(r_seed)
    torch.manual_seed(r_seed)


def test_end2end(seed=20200202, n_dialogues=1000, nlg='TemplateNLG'):
    # go to README.md of each model for more information
    # BERT nlu
    sys_nlu = BERTNLU()
    # simple rule DST
    sys_dst = RuleDST()
    # rule policy
    sys_policy = RulePolicy()
    # template NLG
    #sys_nlg = [sys_nlg_template, sys_nlg_sclstm, sys_nlg_scgpt]
    
    # BERT nlu trained on sys utterance
    user_nlu = BERTNLU(mode='sys', config_file='multiwoz_sys_context.json',
                       model_file='https://convlab.blob.core.windows.net/convlab-2/bert_multiwoz_sys_context.zip')
    # not use dst
    user_dst = None
    # rule policy
    user_policy = RulePolicy(character='usr')
    # NLG
    user_nlg_template = TemplateNLG(is_user=True)
    # user_nlg_sclstm = SCLSTM(is_user=True)
    # user_nlg_scgpt = SCGPT(is_user=True)
    # user_nlg = [user_nlg_template, user_nlg_sclstm, user_nlg_scgpt]
    # assemble

    print('Using ' + nlg)
    if nlg == 'TemplateNLG':
        sys_nlg = TemplateNLG(is_user=False)
    elif nlg == 'SCLSTM':
        sys_nlg = SCLSTM(is_user=False, use_cuda=True)
    elif nlg == 'SCGPT':
        sys_nlg = SCGPT(is_user=False, model_file='../convlab2/nlg/scgpt/trained_output/multiwoz/')
    else:
        return ('Cannot find module '+ nlg)


    user_agent = PipelineAgent(user_nlu, user_dst, user_policy, user_nlg_template, name='user')
    sys_agent = PipelineAgent(sys_nlu, sys_dst, sys_policy, sys_nlg, name='sys')
    analyzer = Analyzer(user_agent=user_agent, dataset='multiwoz')

    set_seed(seed)
    name=f'BERTNLU-RuleDST-RulePolicy-TemplateNLG-Seed{seed}'
    analyzer.comprehensive_analyze(sys_agent=sys_agent, model_name=(type(sys_nlg).__name__), total_dialog=n_dialogues)


if __name__ == '__main__':
    # Get arguments
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('--seed', help='Seed', default=20200202, type=int)
    parser.add_argument('--n_dialogues', help='Number of eval dialogues', default=1000, type=int)
    parser.add_argument('--sys_nlg', help='system nlg', default='TemplateNLG', type=str)
    args = parser.parse_args()
    seeds = [20200202]
#20200203, 20200204, 20200205, 20200206
    for seed in seeds:
        test_end2end(seed=seed, n_dialogues=args.n_dialogues, nlg=args.sys_nlg)