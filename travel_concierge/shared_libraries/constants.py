# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Constants used as keys into ADK's session state."""

SYSTEM_TIME = "_time"
STAY_INITIALIZED = "_stay_initialized"

STAY_KEY = "stay_record"       # StayRecord JSON in session state
PROF_KEY = "user_profile"      # guest profile dict in session state

STAY_CHECK_IN = "stay_check_in_date"   # YYYY-MM-DD, for prompt template injection
STAY_CHECK_OUT = "stay_check_out_date"
