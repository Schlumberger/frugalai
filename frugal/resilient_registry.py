# frugal/resilient_registry.py
# see LICENSE

import json
from pathlib import Path
from datetime import datetime

from frugal.resumable_registry import ResumableRegistry
from frugal.resilient import ResilienceEngine, TaskProfile, UserTaskState


class ResilientRegistry(ResumableRegistry):
    def __init__( self, base_registry, profile_folder="resilience", default_user="default",
                  user_profiles_json="user_profiles.json", task_profiles_json="task_profiles.json"):
        super().__init__(base_registry)
        self.resilience_engine = ( ResilienceEngine())
        self.default_user = ( default_user )
        self.profile_folder = ( Path(profile_folder) )
        self.profile_folder.mkdir( exist_ok=True )

        # collect task profiles
        self.task_profiles_file = (self.profile_folder/task_profiles_json)
        # collect user profiles
        self.user_profiles_file = (self.profile_folder/user_profiles_json)

        self.load_profiles()

    # --------------------------------
    # private method : record keeping
    # --------------------------------
    def _record_execution(self, task_name, success=True, manual=False,
                          completion_time=None, assistance_used=False):
        # For TESTING
        print("_record_execution")
        user = self.current_user()
        record = self.user_profiles[user][task_name]

        # --------------------
        # initialize fields
        # --------------------
        record.setdefault( "executions_count", 0)
        record.setdefault( "success_count", 0)
        record.setdefault( "assisted_count", 0)
        record.setdefault( "recent_failures", 0)
        record.setdefault( "success_rate", 1.0)
        record.setdefault( "assistance_ratio", 0.0)
        record.setdefault( "avg_completion_time", 0.0)

        # --------------------
        # execution count
        # --------------------
        old_count = (record["executions_count"])
        new_count = old_count + 1
        record["executions_count"] = new_count

        # --------------------
        # success tracking
        # --------------------
        if success:
            record["success_count"] += 1
            record["recent_failures"] = 0
        else:
            record["recent_failures"] += 1

        # --------------------
        # success rate
        # --------------------
        record["success_rate"] = record["success_count"]/new_count

        # --------------------
        # assistance tracking
        # --------------------
        if assistance_used:
            record["assisted_count"] += 1
        record["assistance_ratio"] = record["assisted_count"]/new_count

        # --------------------
        # completion time
        # --------------------
        if completion_time is not None:
            old_avg = record["avg_completion_time"]
            record["avg_completion_time"] =( ( old_avg * old_count ) + completion_time ) / new_count

        # --------------------
        # manual competency
        # refreshes skill
        # --------------------
        if manual:
            record["last_manual_execution"] = datetime.utcnow().isoformat()

        self.save_user_profiles()
        

    # ----------------------------
    # profile handling
    # ----------------------------
    def load_profiles(self):
        # For testing
        print("load_profiles")
        with open( self.task_profiles_file, encoding="utf-8" ) as f:
            self.task_profiles = json.load(f)
        with open( self.user_profiles_file, encoding="utf-8" ) as f:
            self.user_profiles = json.load(f)

    def save_user_profiles(self):
        # For testing
        print("save_user_profiles")
        with open( self.user_profiles_file, "w", encoding="utf-8") as f:
            json.dump(self.user_profiles, f, indent=2)

    # ----------------------------
    # identity
    # ----------------------------
    def current_user(self):
        # for testing
        print("current_user")
        return self.default_user

    # ----------------------------
    # task profile
    # ----------------------------

    def get_task_profile( self, task_name):
        # For testing
        print("get_task_profiles")
        cfg = self.task_profiles[task_name]
        return TaskProfile.from_dict(task_name, cfg)
        
    # ----------------------------
    # user state
    # ----------------------------
    def get_user_state(self, task_name):
        # For testing
        print("get_user_state")
        user = self.current_user()
        # for testing
        print(f"{user=} {task_name=}")

        task_data = self.user_profiles[user][task_name]

        return UserTaskState(user_id=user, task_id=task_name,
                             last_manual_execution_ts=datetime.fromisoformat(task_data["last_manual_execution"]),
                             executions_count= task_data["executions_count"],
                             success_rate=task_data["success_rate"],
                             avg_completion_time=task_data["avg_completion_time"],
                             assistance_ratio=task_data["assistance_ratio"],
                             recent_failures=task_data["recent_failures"])

    # ----------------------------
    # manual execution
    # ----------------------------
    def record_manual_execution(self, task_name, success=True, completion_time=None):
        self._record_execution(task_name=task_name,success=success,manual=True,
                               completion_time=completion_time,assistance_used=False)

    # ----------------------------
    # automated execution
    # ----------------------------
    def record_automated_execution(self,task_name,success=True,completion_time=None,assistance_used=False):
        self._record_execution(task_name=task_name,success=success,manual=False,completion_time=completion_time,
                               assistance_used=assistance_used)

    # ----------------------------
    # interrupt generation
    # ----------------------------
    def trigger_competency_interrupt(self,agent_name,input_text,score):
        # For testing
        print("trigger_competency_interrupt")
        responses = {}
        if (self.state and isinstance(self.state, dict)):
            responses = self.state.get("responses",{})
        
        workflow_state = {"current_node": agent_name, "responses": responses,
                          "human_response": None, "failed_input": input_text,
                          "interrupt_reason": "competency", "score": score,
                          "created": datetime.utcnow().isoformat()}

        sid = self.save_state(workflow_state)
        self.interrupt = {"reason": "competency", "state_id": sid, "node": agent_name,
                          "score": score, "failed_input": input_text}

    def _before_agent_execution(self, agent_name, input_text):
        task = self.get_task_profile(agent_name)
        state = self.get_user_state(agent_name)

        decision = (self.resilience_engine.decision(task,state,datetime.utcnow()))
        print(f"{decision=}")
        
        if decision == "FORCE_MANUAL":
            self.trigger_competency_interrupt(agent_name,input_text,score="high")
            return "INTERRUPT"
        return None

