Build a simple agent that

(1) takes a goal, 
(2) selects tools, 
(3) stores what it learned, 
(4) continues across multiple sessions.

Our agent is going to be used for DV360 only. Think of it as an AI DV360 strategist sitting next to you, continuously reviewing and proposing actions while you stay in control.    

                 ┌────────────────────────┐
                 │  Chat Conductor Agent  │
                 │ (you talk to this one) │
                 └──────────┬─────────────┘
                            │
        ┌──────────┬─────────┴─────────┬──────────┐
        │           │                   │          │
┌───────▼──────┐ ┌──▼─────────┐ ┌──────▼─────┐ ┌──▼──────────┐
│ Performance  │ │ Budget &   │ │ Audience & │ │ Creative &  │
│ Diagnosis    │ │ Pacing     │ │ Targeting  │ │ Inventory   │
│ Agent        │ │ Agent      │ │ Agent      │ │ Agent       │
└──────────────┘ └────────────┘ └────────────┘ └─────────────┘

Tools to use Langgraph mainly all in python

We want an interface 

Docker deployment 

All data will be pulled from snowflake

Full tracking at each stage of the decisions of the agent.

we need to keep growing memory and state

Tools will be 
memory and growing intellignece
seasonality context tool
snowflake tools for pulling the correct data    

