# -*- coding: utf-8 -*-
"""Restart-safe persistence for the Dark World."""
from datetime import datetime
from sqlalchemy import BigInteger,Boolean,DateTime,Integer,String,UniqueConstraint,func
from sqlalchemy.orm import Mapped,mapped_column
from app.database.base import Base
class DarkWorldProfile(Base):
 __tablename__="dark_world_profiles"
 tg_user_id:Mapped[int]=mapped_column(BigInteger,primary_key=True)
 dark_xp:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
 influence:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0,index=True)
 heat:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 energy:Mapped[int]=mapped_column(Integer,nullable=False,default=100)
 intel:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 contracts_started:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 successes:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 failures:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 current_streak:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 best_streak:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 cash_earned:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
 last_energy_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow)
 last_heat_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow)
 active_contract_key:Mapped[str|None]=mapped_column(String(32),nullable=True)
 active_approach_key:Mapped[str|None]=mapped_column(String(24),nullable=True)
 active_started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 active_ready_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 active_success:Mapped[bool|None]=mapped_column(Boolean,nullable=True)
 active_cash:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
 active_xp:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 active_dark_xp:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 active_influence:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 active_heat:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 active_intel:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 active_chance_bp:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 active_roll_bp:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
 updated_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now(),onupdate=func.now())
class DarkWorldRecruit(Base):
 __tablename__="dark_world_recruits"; __table_args__=(UniqueConstraint("owner_id","recruit_key",name="uq_dark_world_recruit_owner_key"),)
 id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
 owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True)
 recruit_key:Mapped[str]=mapped_column(String(32),nullable=False)
 level:Mapped[int]=mapped_column(Integer,nullable=False,default=1)
 loyalty:Mapped[int]=mapped_column(Integer,nullable=False,default=100)
 missions:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 hired_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
class DarkWorldContractLog(Base):
 __tablename__="dark_world_contract_logs"
 id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
 owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True)
 contract_key:Mapped[str]=mapped_column(String(32),nullable=False)
 approach_key:Mapped[str]=mapped_column(String(24),nullable=False)
 difficulty:Mapped[int]=mapped_column(Integer,nullable=False)
 success:Mapped[bool]=mapped_column(Boolean,nullable=False)
 chance_bp:Mapped[int]=mapped_column(Integer,nullable=False)
 roll_bp:Mapped[int]=mapped_column(Integer,nullable=False)
 cash_reward:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
 xp_reward:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 dark_xp_reward:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 influence_delta:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 heat_delta:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 intel_delta:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 started_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
 completed_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow)


class DarkWorldCaseRun(Base):
    """One restart-safe branching case in progress per user."""
    __tablename__ = "dark_world_case_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, unique=True, index=True)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    beneficiary_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    employment_contract_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    case_key: Mapped[str] = mapped_column(String(32), nullable=False)
    node_key: Mapped[str] = mapped_column(String(32), nullable=False)
    momentum: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    danger: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_tool_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    history_json: Mapped[str] = mapped_column(String(8192), nullable=False, default="[]")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class DarkWorldToolInventory(Base):
    __tablename__ = "dark_world_tool_inventory"
    __table_args__ = (
        UniqueConstraint("owner_id", "tool_key", name="uq_dark_world_tool_owner_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tool_key: Mapped[str] = mapped_column(String(32), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DarkWorldCaseLog(Base):
    __tablename__ = "dark_world_case_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    beneficiary_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    employment_contract_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    case_key: Mapped[str] = mapped_column(String(32), nullable=False)
    ending_key: Mapped[str] = mapped_column(String(32), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_checks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peak_danger: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cash_reward: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dark_xp_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    influence_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    heat_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intel_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)


class DarkWorldHideout(Base):
    __tablename__ = "dark_world_hideouts"
    owner_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    integrity: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    forged_ids: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    threat_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    threat_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    threat_roll_bp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clue_order_json: Mapped[str] = mapped_column(String(4096), nullable=False, default="[]")
    clues_json: Mapped[str] = mapped_column(String(4096), nullable=False, default="[]")
    prison_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    prison_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evaded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_evades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class DarkWorldPursuitLog(Base):
    __tablename__ = "dark_world_pursuit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    threat_key: Mapped[str] = mapped_column(String(32), nullable=False)
    action_key: Mapped[str] = mapped_column(String(32), nullable=False)
    clue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    chance_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    roll_bp: Mapped[int] = mapped_column(Integer, nullable=False)
    heat_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jailed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class DarkWorldRecruitState(Base):
 __tablename__="dark_world_recruit_states";__table_args__=(UniqueConstraint("owner_id","recruit_key",name="uq_dw_recruit_state"),)
 id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
 owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);recruit_key:Mapped[str]=mapped_column(String(32),nullable=False)
 fatigue:Mapped[int]=mapped_column(Integer,nullable=False,default=0);unpaid_cycles:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 wage_due_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True);training_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 rest_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True);injured_until:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 deserted:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False)
class DarkWorldTeam(Base):
 __tablename__="dark_world_teams";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True)
 member_keys_json:Mapped[str]=mapped_column(String(512),nullable=False,default="[]");tactic_key:Mapped[str]=mapped_column(String(24),nullable=False,default="balanced")
class DarkWorldRecruitEvent(Base):
 __tablename__="dark_world_recruit_events";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
 owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);recruit_key:Mapped[str]=mapped_column(String(32),nullable=False)
 event_key:Mapped[str]=mapped_column(String(32),nullable=False);value:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
 created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())


class DarkWorldEmploymentContract(Base):
 __tablename__="dark_world_employment_contracts"
 id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)
 employer_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);worker_id:Mapped[int|None]=mapped_column(BigInteger,nullable=True,index=True);beneficiary_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True)
 job_key:Mapped[str]=mapped_column(String(32),nullable=False);payment_key:Mapped[str]=mapped_column(String(16),nullable=False);status:Mapped[str]=mapped_column(String(20),nullable=False,index=True);condition_key:Mapped[str]=mapped_column(String(20),nullable=False)
 min_level:Mapped[int]=mapped_column(Integer,nullable=False,default=35);min_trust:Mapped[int]=mapped_column(Integer,nullable=False,default=35)
 fixed_wage:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);success_bonus:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);share_pct:Mapped[int]=mapped_column(Integer,nullable=False,default=0);operation_budget:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);escrow_total:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
 execution_approach:Mapped[str|None]=mapped_column(String(20),nullable=True);execution_chance_bp:Mapped[int]=mapped_column(Integer,nullable=False,default=0);execution_roll_bp:Mapped[int]=mapped_column(Integer,nullable=False,default=0);result_success:Mapped[bool|None]=mapped_column(Boolean,nullable=True);result_loot:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);result_effect:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
 worker_payout:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);employer_refund:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);disputed_by:Mapped[int|None]=mapped_column(BigInteger,nullable=True);disputed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
 created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now(),index=True);expires_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True);accepted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True);started_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True);submitted_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True);completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldEmploymentReputation(Base):
 __tablename__="dark_world_employment_reputations";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True);trust:Mapped[int]=mapped_column(Integer,nullable=False,default=50);contracts_as_employer:Mapped[int]=mapped_column(Integer,nullable=False,default=0);contracts_as_worker:Mapped[int]=mapped_column(Integer,nullable=False,default=0);successes:Mapped[int]=mapped_column(Integer,nullable=False,default=0);failures:Mapped[int]=mapped_column(Integer,nullable=False,default=0);disputes:Mapped[int]=mapped_column(Integer,nullable=False,default=0);amount_earned:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);amount_paid:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
class DarkWorldEmploymentLog(Base):
 __tablename__="dark_world_employment_logs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);contract_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);actor_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);event_key:Mapped[str]=mapped_column(String(32),nullable=False);amount:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())


class DarkWorldSmugglingProfile(Base):
 __tablename__="dark_world_smuggling_profiles";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True);warehouse_level:Mapped[int]=mapped_column(Integer,nullable=False,default=1);shipments:Mapped[int]=mapped_column(Integer,nullable=False,default=0);successes:Mapped[int]=mapped_column(Integer,nullable=False,default=0);cash_earned:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
class DarkWorldSmugglingInventory(Base):
 __tablename__="dark_world_smuggling_inventory";__table_args__=(UniqueConstraint("owner_id","good_key",name="uq_dw_smuggle_inv"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);good_key:Mapped[str]=mapped_column(String(16),nullable=False);qty:Mapped[int]=mapped_column(Integer,nullable=False,default=0);cost_basis:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
class DarkWorldShipment(Base):
 __tablename__="dark_world_shipments";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);good_key:Mapped[str]=mapped_column(String(16),nullable=False);qty:Mapped[int]=mapped_column(Integer,nullable=False);pack_key:Mapped[str]=mapped_column(String(16),nullable=False);route_key:Mapped[str]=mapped_column(String(16),nullable=False);dest_key:Mapped[str]=mapped_column(String(16),nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False);result_success:Mapped[bool]=mapped_column(Boolean,nullable=False);result_cash:Mapped[int]=mapped_column(BigInteger,nullable=False);result_heat:Mapped[int]=mapped_column(Integer,nullable=False);started_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);ready_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldMarketOffer(Base):
 __tablename__="dark_world_market_offers";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);seller_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);good_key:Mapped[str]=mapped_column(String(16),nullable=False,index=True);total_qty:Mapped[int]=mapped_column(Integer,nullable=False);remaining_qty:Mapped[int]=mapped_column(Integer,nullable=False);price_per_unit:Mapped[int]=mapped_column(BigInteger,nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now());expires_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
class DarkWorldMarketTrade(Base):
 __tablename__="dark_world_market_trades";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);offer_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);seller_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);buyer_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);good_key:Mapped[str]=mapped_column(String(16),nullable=False,index=True);qty:Mapped[int]=mapped_column(Integer,nullable=False);price_per_unit:Mapped[int]=mapped_column(BigInteger,nullable=False);fee:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now(),index=True)


class DarkWorldFinance(Base):
 __tablename__="dark_world_finance";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True);dirty_balance:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);trace:Mapped[int]=mapped_column(Integer,nullable=False,default=0);last_trace_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow);total_dirty_earned:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);total_cleaned:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);total_confiscated:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
class DarkWorldLaunderingJob(Base):
 __tablename__="dark_world_laundering_jobs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);method_key:Mapped[str]=mapped_column(String(16),nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);dirty_amount:Mapped[int]=mapped_column(BigInteger,nullable=False);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False);result_success:Mapped[bool]=mapped_column(Boolean,nullable=False);clean_cash:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);dirty_refund:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);confiscated:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);trace_gain:Mapped[int]=mapped_column(Integer,nullable=False,default=0);started_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);ready_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldRareInventory(Base):
 __tablename__="dark_world_rare_inventory";__table_args__=(UniqueConstraint("owner_id","item_key",name="uq_dw_rare_inv"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);item_key:Mapped[str]=mapped_column(String(32),nullable=False);qty:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldFinanceLog(Base):
 __tablename__="dark_world_finance_logs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);event_key:Mapped[str]=mapped_column(String(40),nullable=False);amount:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);trace_delta:Mapped[int]=mapped_column(Integer,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now(),index=True)


class DarkWorldRaidDefense(Base):
 __tablename__="dark_world_raid_defenses";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True);doctrine_key:Mapped[str]=mapped_column(String(20),nullable=False,default="fortify");updated_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow,onupdate=datetime.utcnow)
class DarkWorldRecon(Base):
 __tablename__="dark_world_recons";__table_args__=(UniqueConstraint("attacker_id","target_id",name="uq_dw_recon_pair"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);attacker_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);target_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);observed_defense:Mapped[str]=mapped_column(String(20),nullable=False);truthful:Mapped[bool]=mapped_column(Boolean,nullable=False);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow);expires_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True)
class DarkWorldRaid(Base):
 __tablename__="dark_world_raids";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);attacker_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);defender_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);approach_key:Mapped[str]=mapped_column(String(20),nullable=False);defense_key:Mapped[str]=mapped_column(String(20),nullable=False);status:Mapped[str]=mapped_column(String(20),nullable=False,index=True);stake:Mapped[int]=mapped_column(BigInteger,nullable=False);recon_truthful:Mapped[bool]=mapped_column(Boolean,nullable=False);attack_support_count:Mapped[int]=mapped_column(Integer,nullable=False,default=0);defense_support_count:Mapped[int]=mapped_column(Integer,nullable=False,default=0);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False,default=0);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False,default=0);stolen_amount:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow,index=True);lock_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True);resolved_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldRaidParticipant(Base):
 __tablename__="dark_world_raid_participants";__table_args__=(UniqueConstraint("raid_id","user_id",name="uq_dw_raid_member"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);raid_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);user_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);side:Mapped[str]=mapped_column(String(12),nullable=False);intel_spent:Mapped[int]=mapped_column(Integer,nullable=False,default=0);joined_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
class DarkWorldRaidLog(Base):
 __tablename__="dark_world_raid_logs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);raid_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);actor_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);event_key:Mapped[str]=mapped_column(String(32),nullable=False);side:Mapped[str]=mapped_column(String(12),nullable=False);amount:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())


class DarkWorldSeason(Base):
 __tablename__="dark_world_seasons";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_no:Mapped[int]=mapped_column(Integer,nullable=False,unique=True);title:Mapped[str]=mapped_column(String(80),nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);chapter_index:Mapped[int]=mapped_column(Integer,nullable=False,default=0);chapter_ends_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True);market_bias:Mapped[int]=mapped_column(Integer,nullable=False,default=0);finance_bias:Mapped[int]=mapped_column(Integer,nullable=False,default=0);raid_bias:Mapped[int]=mapped_column(Integer,nullable=False,default=0);last_choice_key:Mapped[str|None]=mapped_column(String(24),nullable=True);winning_faction:Mapped[str|None]=mapped_column(String(16),nullable=True);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow);completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldFactionMember(Base):
 __tablename__="dark_world_faction_members";__table_args__=(UniqueConstraint("owner_id","season_id",name="uq_dw_season_member"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);faction_key:Mapped[str]=mapped_column(String(16),nullable=False,index=True);contribution:Mapped[int]=mapped_column(Integer,nullable=False,default=0);reward_claimed:Mapped[bool]=mapped_column(Boolean,nullable=False,default=False);joined_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow)
class DarkWorldSeasonVote(Base):
 __tablename__="dark_world_season_votes";__table_args__=(UniqueConstraint("season_id","chapter_index","owner_id",name="uq_dw_chapter_vote"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);chapter_index:Mapped[int]=mapped_column(Integer,nullable=False);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);faction_key:Mapped[str]=mapped_column(String(16),nullable=False);choice_key:Mapped[str]=mapped_column(String(24),nullable=False);weight:Mapped[int]=mapped_column(Integer,nullable=False,default=1);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
class DarkWorldFactionScore(Base):
 __tablename__="dark_world_faction_scores";__table_args__=(UniqueConstraint("season_id","faction_key",name="uq_dw_faction_score"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);faction_key:Mapped[str]=mapped_column(String(16),nullable=False);points:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0)
class DarkWorldSeasonLog(Base):
 __tablename__="dark_world_season_logs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);chapter_index:Mapped[int]=mapped_column(Integer,nullable=False);event_key:Mapped[str]=mapped_column(String(32),nullable=False);detail_key:Mapped[str]=mapped_column(String(32),nullable=False);value:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())


class DarkWorldSeasonRank(Base):
 __tablename__="dark_world_season_ranks";__table_args__=(UniqueConstraint("season_id","owner_id",name="uq_dw_season_rank"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);faction_key:Mapped[str]=mapped_column(String(16),nullable=False);rank:Mapped[int]=mapped_column(Integer,nullable=False,index=True);score:Mapped[int]=mapped_column(BigInteger,nullable=False);division_key:Mapped[str]=mapped_column(String(24),nullable=False);eligible:Mapped[bool]=mapped_column(Boolean,nullable=False);activity:Mapped[int]=mapped_column(Integer,nullable=False);shipments:Mapped[int]=mapped_column(Integer,nullable=False,default=0);launders:Mapped[int]=mapped_column(Integer,nullable=False,default=0);raid_wins:Mapped[int]=mapped_column(Integer,nullable=False,default=0);employment:Mapped[int]=mapped_column(Integer,nullable=False,default=0);boss_damage:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);influence_snapshot:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);contribution_snapshot:Mapped[int]=mapped_column(Integer,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
class DarkWorldCompetitiveProfile(Base):
 __tablename__="dark_world_competitive_profiles";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True);rating:Mapped[int]=mapped_column(Integer,nullable=False,default=0,index=True);prestige:Mapped[int]=mapped_column(Integer,nullable=False,default=0);seasons:Mapped[int]=mapped_column(Integer,nullable=False,default=0);best_rank:Mapped[int|None]=mapped_column(Integer,nullable=True);last_title:Mapped[str|None]=mapped_column(String(40),nullable=True)
class DarkWorldCompetitiveReward(Base):
 __tablename__="dark_world_competitive_rewards";__table_args__=(UniqueConstraint("season_id","owner_id",name="uq_dw_comp_reward"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);rank:Mapped[int]=mapped_column(Integer,nullable=False);dirty_reward:Mapped[int]=mapped_column(BigInteger,nullable=False);intel_reward:Mapped[int]=mapped_column(Integer,nullable=False);prestige_reward:Mapped[int]=mapped_column(Integer,nullable=False);title_key:Mapped[str]=mapped_column(String(40),nullable=False);claimed_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
class DarkWorldBalanceSnapshot(Base):
 __tablename__="dark_world_balance_snapshots";season_id:Mapped[int]=mapped_column(Integer,primary_key=True);dirty_created:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);cleaned:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);confiscated:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);market_volume:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);reward_factor_bp:Mapped[int]=mapped_column(Integer,nullable=False,default=10000);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False)
class DarkWorldWorldBoss(Base):
 __tablename__="dark_world_world_bosses";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,unique=True,index=True);name:Mapped[str]=mapped_column(String(40),nullable=False);max_hp:Mapped[int]=mapped_column(BigInteger,nullable=False);current_hp:Mapped[int]=mapped_column(BigInteger,nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);defeated_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldBossHit(Base):
 __tablename__="dark_world_boss_hits";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);season_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);boss_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);damage:Mapped[int]=mapped_column(BigInteger,nullable=False);roll:Mapped[int]=mapped_column(Integer,nullable=False);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True)


class DarkWorldLab(Base):
 __tablename__="dark_world_labs";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True);level:Mapped[int]=mapped_column(Integer,nullable=False,default=1);equipment:Mapped[int]=mapped_column(Integer,nullable=False,default=1);power:Mapped[int]=mapped_column(Integer,nullable=False,default=1);ventilation:Mapped[int]=mapped_column(Integer,nullable=False,default=1);safety:Mapped[int]=mapped_column(Integer,nullable=False,default=1);condition:Mapped[int]=mapped_column(Integer,nullable=False,default=100);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
class DarkWorldLabMaterial(Base):
 __tablename__="dark_world_lab_materials";__table_args__=(UniqueConstraint("owner_id","material_key",name="uq_dw_lab_material"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);material_key:Mapped[str]=mapped_column(String(16),nullable=False);qty:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldProductInventory(Base):
 __tablename__="dark_world_product_inventory";__table_args__=(UniqueConstraint("owner_id","product_key",name="uq_dw_product_inventory"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);product_key:Mapped[str]=mapped_column(String(24),nullable=False,index=True);qty:Mapped[int]=mapped_column(Integer,nullable=False,default=0);avg_quality:Mapped[int]=mapped_column(Integer,nullable=False,default=0);avg_potency:Mapped[int]=mapped_column(Integer,nullable=False,default=0);avg_stability:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldProductionBatch(Base):
 __tablename__="dark_world_production_batches";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);product_key:Mapped[str]=mapped_column(String(24),nullable=False,index=True);mode_key:Mapped[str]=mapped_column(String(16),nullable=False);input_qty:Mapped[int]=mapped_column(Integer,nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False);result_success:Mapped[bool]=mapped_column(Boolean,nullable=False);result_qty:Mapped[int]=mapped_column(Integer,nullable=False);result_quality:Mapped[int]=mapped_column(Integer,nullable=False);result_potency:Mapped[int]=mapped_column(Integer,nullable=False);result_stability:Mapped[int]=mapped_column(Integer,nullable=False);accident:Mapped[bool]=mapped_column(Boolean,nullable=False);condition_loss:Mapped[int]=mapped_column(Integer,nullable=False);started_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);ready_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True);completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldLabLog(Base):
 __tablename__="dark_world_lab_logs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);event_key:Mapped[str]=mapped_column(String(40),nullable=False);value:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())


class DarkWorldIngredientInventory(Base):
 __tablename__="dark_world_ingredient_inventory";__table_args__=(UniqueConstraint("owner_id","ingredient_key",name="uq_dw_ingredient_inventory"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);ingredient_key:Mapped[str]=mapped_column(String(24),nullable=False,index=True);qty:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldCropPlot(Base):
 __tablename__="dark_world_crop_plots";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);slot_no:Mapped[int]=mapped_column(Integer,nullable=False);base_key:Mapped[str]=mapped_column(String(24),nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);yield_qty:Mapped[int]=mapped_column(Integer,nullable=False);planted_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);ready_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True);harvested_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldCustomRecipe(Base):
 __tablename__="dark_world_custom_recipes";__table_args__=(UniqueConstraint("owner_id","fingerprint",name="uq_dw_custom_recipe"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);fingerprint:Mapped[str]=mapped_column(String(20),nullable=False,index=True);base_key:Mapped[str]=mapped_column(String(24),nullable=False);catalyst_key:Mapped[str]=mapped_column(String(24),nullable=False);signature_key:Mapped[str]=mapped_column(String(24),nullable=False);brand_key:Mapped[str]=mapped_column(String(16),nullable=False);custom_name:Mapped[str]=mapped_column(String(80),nullable=False);quality:Mapped[int]=mapped_column(Integer,nullable=False);power:Mapped[int]=mapped_column(Integer,nullable=False);stability:Mapped[int]=mapped_column(Integer,nullable=False);risk:Mapped[int]=mapped_column(Integer,nullable=False);value:Mapped[int]=mapped_column(BigInteger,nullable=False);required_level:Mapped[int]=mapped_column(Integer,nullable=False);discovered_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
class DarkWorldCustomBatch(Base):
 __tablename__="dark_world_custom_batches";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);recipe_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);mode_key:Mapped[str]=mapped_column(String(16),nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False);result_success:Mapped[bool]=mapped_column(Boolean,nullable=False);result_qty:Mapped[int]=mapped_column(Integer,nullable=False);result_quality:Mapped[int]=mapped_column(Integer,nullable=False);result_power:Mapped[int]=mapped_column(Integer,nullable=False);result_stability:Mapped[int]=mapped_column(Integer,nullable=False);condition_loss:Mapped[int]=mapped_column(Integer,nullable=False);started_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);ready_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True);completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldCustomInventory(Base):
 __tablename__="dark_world_custom_inventory";__table_args__=(UniqueConstraint("owner_id","recipe_id",name="uq_dw_custom_inventory"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);recipe_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);qty:Mapped[int]=mapped_column(Integer,nullable=False,default=0);avg_quality:Mapped[int]=mapped_column(Integer,nullable=False,default=0);avg_power:Mapped[int]=mapped_column(Integer,nullable=False,default=0);avg_stability:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldCustomSale(Base):
 __tablename__="dark_world_custom_sales";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);recipe_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);qty:Mapped[int]=mapped_column(Integer,nullable=False);unit_value:Mapped[int]=mapped_column(BigInteger,nullable=False);demand_bonus:Mapped[bool]=mapped_column(Boolean,nullable=False);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now(),index=True)


class DarkWorldDistributionProfile(Base):
 __tablename__="dark_world_distribution_profiles";__table_args__=(UniqueConstraint("owner_id","district_key",name="uq_dw_distribution_profile"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);district_key:Mapped[str]=mapped_column(String(20),nullable=False,index=True);reputation:Mapped[int]=mapped_column(Integer,nullable=False,default=0);control_points:Mapped[int]=mapped_column(Integer,nullable=False,default=0);sales:Mapped[int]=mapped_column(Integer,nullable=False,default=0);failures:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldDistributionSale(Base):
 __tablename__="dark_world_distribution_sales";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);recipe_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);district_key:Mapped[str]=mapped_column(String(20),nullable=False,index=True);channel_key:Mapped[str]=mapped_column(String(20),nullable=False);screen_key:Mapped[str]=mapped_column(String(20),nullable=False);customer_key:Mapped[str]=mapped_column(String(20),nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);qty:Mapped[int]=mapped_column(Integer,nullable=False);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False);result_success:Mapped[bool]=mapped_column(Boolean,nullable=False);caught:Mapped[bool]=mapped_column(Boolean,nullable=False);payout:Mapped[int]=mapped_column(BigInteger,nullable=False);heat_gain:Mapped[int]=mapped_column(Integer,nullable=False);reputation_delta:Mapped[int]=mapped_column(Integer,nullable=False);started_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);ready_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True);completed_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldCustomerContact(Base):
 __tablename__="dark_world_customer_contacts";__table_args__=(UniqueConstraint("owner_id","district_key","customer_key",name="uq_dw_customer_contact"),);id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);district_key:Mapped[str]=mapped_column(String(20),nullable=False);customer_key:Mapped[str]=mapped_column(String(20),nullable=False);trust:Mapped[int]=mapped_column(Integer,nullable=False,default=0);debt:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);deals:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldDistributionLog(Base):
 __tablename__="dark_world_distribution_logs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);sale_id:Mapped[int]=mapped_column(Integer,nullable=False,index=True);event_key:Mapped[str]=mapped_column(String(24),nullable=False);value:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())


class DarkWorldEmpireProfile(Base):
 __tablename__="dark_world_empire_profiles";owner_id:Mapped[int]=mapped_column(BigInteger,primary_key=True);research_points:Mapped[int]=mapped_column(Integer,nullable=False,default=0);brand_power:Mapped[int]=mapped_column(Integer,nullable=False,default=0);rival_wins:Mapped[int]=mapped_column(Integer,nullable=False,default=0);inspection_wins:Mapped[int]=mapped_column(Integer,nullable=False,default=0);total_capacity:Mapped[int]=mapped_column(Integer,nullable=False,default=0)
class DarkWorldFacility(Base):
 __tablename__="dark_world_facilities";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);facility_key:Mapped[str]=mapped_column(String(24),nullable=False);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);capacity_level:Mapped[int]=mapped_column(Integer,nullable=False,default=0);stealth_level:Mapped[int]=mapped_column(Integer,nullable=False,default=0);resilience_level:Mapped[int]=mapped_column(Integer,nullable=False,default=0);research_level:Mapped[int]=mapped_column(Integer,nullable=False,default=0);condition:Mapped[int]=mapped_column(Integer,nullable=False,default=100);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow)
class DarkWorldRivalConflict(Base):
 __tablename__="dark_world_rival_conflicts";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);rival_key:Mapped[str]=mapped_column(String(20),nullable=False);response_key:Mapped[str]=mapped_column(String(20),nullable=False);result_success:Mapped[bool]=mapped_column(Boolean,nullable=False);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False);control_delta:Mapped[int]=mapped_column(Integer,nullable=False);reward:Mapped[int]=mapped_column(BigInteger,nullable=False);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,index=True)
class DarkWorldInspection(Base):
 __tablename__="dark_world_inspections";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);status:Mapped[str]=mapped_column(String(16),nullable=False,index=True);risk_bp:Mapped[int]=mapped_column(Integer,nullable=False);choice_key:Mapped[str|None]=mapped_column(String(20),nullable=True);chance_bp:Mapped[int]=mapped_column(Integer,nullable=False);roll_bp:Mapped[int]=mapped_column(Integer,nullable=False);result_success:Mapped[bool]=mapped_column(Boolean,nullable=False);condition_loss:Mapped[int]=mapped_column(Integer,nullable=False);confiscated_qty:Mapped[int]=mapped_column(Integer,nullable=False);warned_at:Mapped[datetime]=mapped_column(DateTime,nullable=False);ready_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True,index=True);resolved_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
class DarkWorldEmpireLog(Base):
 __tablename__="dark_world_empire_logs";id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True);owner_id:Mapped[int]=mapped_column(BigInteger,nullable=False,index=True);event_key:Mapped[str]=mapped_column(String(32),nullable=False);value:Mapped[int]=mapped_column(BigInteger,nullable=False,default=0);created_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,server_default=func.now())
