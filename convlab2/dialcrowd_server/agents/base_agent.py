'''

Build up an pipeline agent with nlu, dst, policy and nlg.

@author: Chris Geishauser
'''

from convlab2.dialog_agent.agent import DialogueAgent


class BaseAgent(DialogueAgent):

    def __init__(self, config, policy_sys):

        nlu = config['nlu_sys_activated']
        dst = config['dst_sys_activated']
        nlg = config['sys_nlg_activated']

        super().__init__(nlu, dst, policy_sys, nlg)
