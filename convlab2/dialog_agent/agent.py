"""Dialog agent interface and classes."""
from abc import ABC, abstractmethod
import logging
from convlab2.nlu import NLU
from convlab2.dst import DST
from convlab2.policy import Policy
from convlab2.nlg import NLG
from copy import deepcopy
import time
from pprint import pprint


class Agent(ABC):
    """Interface for dialog agent classes."""

    @abstractmethod
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def response(self, observation):
        """Generate agent response given user input.

        The data type of input and response can be either str or list of tuples, condition on the form of agent.

        Example:
            If the agent is a pipeline agent with NLU, DST and Policy, then type(input) == str and
            type(response) == list of tuples.
        Args:
            observation (str or list of tuples):
                The input to the agent.
        Returns:
            response (str or list of tuples):
                The response generated by the agent.
        """
        pass

    @abstractmethod
    def init_session(self, **kwargs):
        """Reset the class variables to prepare for a new session."""
        pass


class PipelineAgent(Agent):

    """Pipeline dialog agent base class, including NLU, DST, Policy and NLG.

    The combination modes of pipeline agent modules are flexible. The only thing you have to make sure is that
    the API of agents are matched.

    Example:
        If agent A is (nlu, tracker, policy), then the agent B should be like (tracker, policy, nlg) to ensure API
        matching.
    The valid module combinations are as follows:
           =====   =====    ======  ===     ==      ===
            NLU     DST     Policy  NLG     In      Out
           =====   =====    ======  ===     ==      ===
            \+      \+        \+    \+      nl      nl
             o      \+        \+    \+      da      nl
             o      \+        \+     o      da      da
            \+      \+        \+     o      nl      da
             o       o        \+     o      da      da
           =====   =====    ======  ===     ==      ===
    """

    def __init__(self, nlu: NLU, dst: DST, policy: Policy, nlg: NLG, name: str, return_semantic_acts=False):
        """The constructor of PipelineAgent class.

        Here are some special combination cases:

            1. If you use word-level DST (such as Neural Belief Tracker), you should set the nlu_model paramater \
             to None. The agent will combine the modules automitically.

            2. If you want to aggregate DST and Policy as a single module, set tracker to None.

        Args:
            nlu (NLU):
                The natural language understanding module of agent.

            dst (DST):
                The dialog state tracker of agent.

            policy (Policy):
                The dialog policy module of agent.

            nlg (NLG):
                The natural language generator module of agent.

        """
        super(PipelineAgent, self).__init__(name=name)
        assert self.name in ['user', 'sys']
        self.opponent_name = 'user' if self.name == 'sys' else 'sys'
        self.nlu = nlu
        self.dst = dst
        self.policy = policy
        self.nlg = nlg
        self.return_semantic_acts = return_semantic_acts
        self.init_session()
        self.agent_saves = []
        self.history = []
        self.turn = 0
        self.cur_domain = None

        #logging.info("Pipeline Agent info_dict check")
        if hasattr(self.nlu, 'info_dict') == False:
            logging.warning('nlu info_dict is not initialized')
        if hasattr(self.dst, 'info_dict') == False:
            logging.warning('dst info_dict is not initialized')
        if hasattr(self.policy, 'info_dict') == False:
            logging.warning('policy info_dict is not initialized')
        if hasattr(self.nlg, 'info_dict') == False:
            logging.warning('nlg info_dict is not initialized')
        #logging.info("Done")

    def state_replace(self, agent_state):
        """
        this interface is reserved to replace all interal states of agent
        the code snippet example below is for the scenario when the agent state only depends on self.history and self.dst.state
        """
        self.history = deepcopy(agent_state['history'])
        self.dst.state = deepcopy(agent_state['dst_state'])

    def state_return(self):
        """
        this interface is reserved to return all interal states of agent
        the code snippet example below is for the scenario when the agent state only depends on self.history and self.dst.state
        """
        agent_state = {}
        agent_state['history'] = deepcopy(self.history)
        agent_state['dst_state'] = deepcopy(self.dst.state)

        return agent_state

    def response(self, observation):
        """Generate agent response using the agent modules."""
        # Note: If you modify the logic of this function, please ensure that it is consistent with deploy.server.ServerCtrl._turn()
        if self.dst is not None:
            # [['sys', sys_utt], ['user', user_utt],...]
            self.dst.state['history'].append([self.opponent_name, observation])
        self.history.append([self.opponent_name, observation])
        # get dialog act
        if self.name == 'sys':
            if self.nlu is not None:
                self.input_action = self.nlu.predict(
                    observation, context=[x[1] for x in self.history[:-1]])
            else:
                self.input_action = observation
        else:
            if self.nlu is not None:
                self.input_action_eval = self.nlu.predict(
                    observation, context=[x[1] for x in self.history[:-1]])

                self.input_action = self.nlu.predict(
                    observation, context=[x[1] for x in self.history[:-1]])
            else:
                self.input_action = observation
                self.input_action_eval = observation
        # get rid of reference problem
        self.input_action = deepcopy(self.input_action)

        # get state
        if self.dst is not None:
            if self.name == 'sys':
                self.dst.state['user_action'] = self.input_action
            else:
                self.dst.state['system_action'] = self.input_action
            state = self.dst.update(self.input_action)
        else:
            state = self.input_action

        state = deepcopy(state)  # get rid of reference problem
        # get action
        # get rid of reference problem
        self.output_action = deepcopy(self.policy.predict(state))

        # get model response
        if self.nlg is not None:
            model_response = self.nlg.generate(self.output_action)
        else:
            model_response = self.output_action
        # print(model_response)

        if self.dst is not None:
            self.dst.state['history'].append([self.name, model_response])
            if self.name == 'sys':
                self.dst.state['system_action'] = self.output_action
                # If system takes booking action add booking info to the 'book-booked' section of the belief state
                if type(self.input_action) != list:
                    self.input_action = self.dst.state['user_action']
                if type(self.input_action) == list:
                    for intent, domain, slot, value in self.input_action:
                        if domain.lower() not in ['booking', 'general']:
                            self.cur_domain = domain

                if type(self.output_action) == list:
                    for intent, domain, slot, value in self.output_action:
                        if domain.lower() not in ['general', 'booking']:
                            self.cur_domain = domain
                        dial_act = f'{domain.lower()}-{intent.lower()}-{slot.lower()}'
                        if dial_act == 'booking-book-ref' and self.cur_domain.lower() in ['hotel', 'restaurant', 'train']:
                            if self.cur_domain:
                                self.dst.state['belief_state'][self.cur_domain.lower()]['book']['booked'] = [{slot.lower():value}]
                        elif dial_act == 'train-offerbooked-ref' or dial_act == 'train-inform-ref':
                            self.dst.state['belief_state']['train']['book']['booked'] = [{slot.lower():value}]
                        elif dial_act == 'taxi-inform-car':
                            self.dst.state['belief_state']['taxi']['book']['booked'] = [{slot.lower():value}]
            else:
                self.dst.state['user_action'] = self.output_action
                # user dst is also updated by itself
                state = self.dst.update(self.output_action)

        self.history.append([self.name, model_response])

        self.turn += 1
        if self.return_semantic_acts:
            return self.output_action
        self.agent_saves.append(self.save_info())
        return model_response

    def save_info(self):
        try:
            infos = {}
            if hasattr(self.nlu, 'info_dict'):
                infos["nlu"] = self.nlu.info_dict
            if hasattr(self.dst, 'info_dict'):
                infos["dst"] = self.dst.info_dict
            if hasattr(self.policy, 'info_dict'):
                infos["policy"] = self.policy.info_dict
            if hasattr(self.nlg, 'info_dict'):
                infos["nlg"] = self.nlg.info_dict
            # nlu_info = self.agents[agent_id].nlu.info
            # policy_info = self.agents[agent_id].policy.info
            # nlg_info = self.agents[agent_id].nlg.info
            # infos = {"nlu": nlu_info, "policy": policy_info, "nlg": nlg_info}
            # infos = {"nlu": self.turn, "policy": "policy", "nlg": "nlg"}
        except:
            infos = None

        return infos

    def is_terminated(self):
        if hasattr(self.policy, 'is_terminated'):
            return self.policy.is_terminated()
        return None

    def get_reward(self):
        if hasattr(self.policy, 'get_reward'):
            return self.policy.get_reward()
        return None

    def init_session(self, **kwargs):
        """Init the attributes of DST and Policy module."""
        self.cur_domain = None
        if self.nlu is not None:
            self.nlu.init_session()
        if self.dst is not None:
            self.dst.init_session()

            if self.name == 'sys':
                self.dst.state['history'].append(
                    [self.name, 'null'])  # TODO: ??

        if self.policy is not None:
            self.policy.init_session(**kwargs)
        if self.nlg is not None:
            self.nlg.init_session()
        self.history = []

    def get_in_da_eval(self):
        return self.input_action_eval

    def get_in_da(self):
        return self.input_action

    def get_out_da(self):
        return self.output_action


# Agent for Dialogue Server for HHU Dialcrowd. It is an extension of PipelineAgent with minor modification.

class DialogueAgent(Agent):
    """Pipeline dialog agent base class, including NLU, DST, Policy and NLG.
    """

    def __init__(self, nlu: NLU, dst: DST, policy: Policy, nlg: NLG, name: str = "sys"):
        """The constructor of DialogueAgent class.

        Here are some special combination cases:

            1. If you use word-level DST (such as Neural Belief Tracker), you should set the nlu_model parameter \
             to None. The agent will combine the modules automatically.

            2. If you want to aggregate DST and Policy as a single module, set tracker to None.

        Args:
            nlu (NLU):
                The natural language understanding module of agent.

            dst (DST):
                The dialog state tracker of agent.

            policy (Policy):
                The dialog policy module of agent.

            nlg (NLG):
                The natural language generator module of agent.
        """

        super(DialogueAgent, self).__init__(name=name)
        assert self.name in ['sys']
        self.opponent_name = 'user'
        self.nlu = nlu
        self.dst = dst
        self.policy = policy
        self.nlg = nlg
        self.module_names = ["nlu", "dst", "policy", "nlg"]
        self.init_session()
        self.history = []
        self.session_id = None
        self.ENDING_DIALOG = False
        self.USER_RATED = False
        self.USER_GOAL_ACHIEVED = None
        self.taskID = None
        self.feedback = None
        self.requested_feedback = False
        self.sys_state_history = []
        self.sys_action_history = []
        self.sys_utterance_history = []
        self.sys_output_history = []
        self.action_mask_history = []
        self.action_prob_history = []
        self.turn = 0
        self.agent_saves = {"session_id": None, "agent_id": None,
                            "user_id": None, "timestamp": None, "dialogue_info": [], "dialogue_info_fundamental": []}
        self.initTime = int(time.time())
        self.lastUpdate = int(time.time())
        self.cur_domain = None

        logging.info("Dialogue Agent info_dict check")
        if not hasattr(self.nlu, 'info_dict'):
            logging.warning('nlu info_dict is not initialized')
        if not hasattr(self.dst, 'info_dict'):
            logging.warning('dst info_dict is not initialized')
        if not hasattr(self.policy, 'info_dict'):
            logging.warning('policy info_dict is not initialized')
        if not hasattr(self.nlg, 'info_dict'):
            logging.warning('nlg info_dict is not initialized')

    def response(self, observation):
        """Generate agent response using the agent modules."""

        self.sys_utterance_history.append(observation)
        fundamental_info = {'observation': observation}

        if self.dst is not None:
            self.dst.state['history'].append(
                [self.opponent_name, observation])  # [['sys', sys_utt], ['user', user_utt],...]
        self.history.append([self.opponent_name, observation])
        # get dialog act
        if self.nlu is not None:
            self.input_action = self.nlu.predict(
                observation, context=[x[1] for x in self.history[:-1]])
        else:
            self.input_action = observation
        # get rid of reference problem
        self.input_action = deepcopy(self.input_action)
        fundamental_info['input_action'] = self.input_action

        # get state
        if self.dst is not None:
            self.dst.state['user_action'] = self.input_action
            state = self.dst.update(self.input_action)
        else:
            state = self.input_action

        fundamental_info['state'] = state

        state = deepcopy(state)  # get rid of reference problem
        self.sys_state_history.append(state)

        # get action
        # get rid of reference problem
        self.output_action = deepcopy(self.policy.predict(state))
        if hasattr(self.policy, "last_action"):
            self.sys_action_history.append(self.policy.last_action)
        else:
            self.sys_action_history.append(self.output_action)

        fundamental_info['output_action'] = self.output_action

        if hasattr(self.policy, "prob"):
            self.action_prob_history.append(self.policy.prob)

        # get model response
        if self.nlg is not None:
            model_response = self.nlg.generate(self.output_action)
        else:
            model_response = self.output_action

        self.sys_output_history.append(model_response)

        fundamental_info['model_response'] = model_response

        if self.dst is not None:
            self.dst.state['history'].append([self.name, model_response])
            self.dst.state['system_action'] = self.output_action
            # If system takes booking action add booking info to the 'book-booked' section of the belief state
            if type(self.output_action) == list:
                for intent, domain, slot, value in self.output_action:
                    if domain.lower() not in ['general', 'booking']:
                        self.cur_domain = domain
                    dial_act = f'{domain.lower()}-{intent.lower()}-{slot.lower()}'
                    if dial_act == 'booking-book-ref' and self.cur_domain.lower() in ['hotel', 'restaurant', 'train']:
                        if self.cur_domain:
                            self.dst.state['belief_state'][self.cur_domain.lower()]['book']['booked'] = [{slot.lower():value}]
                    elif dial_act == 'train-offerbooked-ref' or dial_act == 'train-inform-ref':
                        self.dst.state['belief_state']['train']['book']['booked'] = [{slot.lower():value}]
                    elif dial_act == 'taxi-inform-car':
                        self.dst.state['belief_state']['taxi']['book']['booked'] = [{slot.lower():value}]
        self.history.append([self.name, model_response])

        self.turn += 1
        self.lastUpdate = int(time.time())

        self.agent_saves['dialogue_info_fundamental'].append(fundamental_info)
        self.agent_saves['dialogue_info'].append(self.get_info())
        return model_response

    def get_info(self):

        info_dict = {}
        for name in self.module_names:
            module = getattr(self, name)
            module_info = getattr(module, "info_dict", None)
            info_dict[name] = module_info

        return info_dict

    def is_terminated(self):
        if hasattr(self.policy, 'is_terminated'):
            return self.policy.is_terminated()
        return None

    def retrieve_reward(self):
        rewards = [1] * len(self.sys_state_history)
        for turn in self.feedback:
            turn_number = int((int(turn) - 2) / 2)
            if turn_number >= len(self.sys_state_history):
                continue
            # TODO possibly use text here to check whether rating belongs to the right utterance of the system
            text = self.feedback[turn]['text']
            rating = self.feedback[turn]["isGood"]
            rewards[turn_number] = int(rating)
        return rewards

    def get_reward(self):
        if hasattr(self.policy, 'get_reward'):
            return self.policy.get_reward()
        return None

    def init_session(self):
        """Init the attributes of DST and Policy module."""
        self.cur_domain = None
        if self.nlu is not None:
            self.nlu.init_session()
        if self.dst is not None:
            self.dst.init_session()
            self.dst.state['history'].append([self.name, 'null'])
        if self.policy is not None:
            self.policy.init_session()
        if self.nlg is not None:
            self.nlg.init_session()
        self.history = []

    def get_in_da(self):
        return self.input_action

    def get_out_da(self):
        return self.output_action

    def print_ending_agent_summary(self):
        print("session_id")
        print(self.session_id)
        print("taskID")
        print(self.taskID)
        print("USER_GOAL_ACHIEVED")
        print(self.USER_GOAL_ACHIEVED)
        print("sys_state_history")
        print(self.sys_state_history)
        print("sys_action_history")
        print(self.sys_action_history)

    def is_inactive(self):
        currentTime = int(time.time())
        return currentTime - self.initTime >= 600 and currentTime - self.lastUpdate >= 60
