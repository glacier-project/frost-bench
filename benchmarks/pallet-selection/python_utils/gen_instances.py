import argparse
import uuid
from frost_planner.core.base import Task, Job, SchedulingInstance, Machine

def _gen_job(job_name: str, task_name: str, requires: list[str], processing_time=45, priority=1) -> Job:
    assert requires, "Requires list cannot be empty"
    task = Task(id=str(uuid.uuid4()), name=task_name, processing_time=processing_time, requires=requires, priority=priority)
    return Job(
        id=str(uuid.uuid4()),
        name=job_name,
        priority=priority,
        tasks=[
            task,
            gen_wait_task(requires=requires, dependencies=[task.id])
        ]
    )

def gen_wait_task(requires: list[str], dependencies: list[str]) -> Task:
    return Task(
        id=str(uuid.uuid4()),
        name="WaitPalletAtSegment",
        processing_time=10,
        requires=requires,
        priority=1,
        dependencies=dependencies
    )

def gen_wh_job() -> Job:
    return _gen_job(
        job_name="ToWarehouseAndBack",
        task_name="ToWarehouseAndBack",
        requires=["store"],
        processing_time=45,
        priority=1
    )

def gen_qc_job() -> Job:
    return _gen_job(
        job_name=f"ToQcAndBack",
        task_name=f"ToQcAndBack",
        requires=["quality_check"],
        processing_time=45,
        priority=1
    )

def gen_rbtc_job() -> Job:
    return _gen_job(
        job_name=f"ToRbtcAndBack",
        task_name=f"ToRbtcAndBack",
        requires=["assemble"],
        processing_time=45,
        priority=1
    )

def gen_mill_job() -> Job:
    return _gen_job(
        job_name=f"ToMillAndBack",
        task_name=f"ToMillAndBack",
        requires=["mill"],
        processing_time=45,
        priority=1
    )

def _gen_machines() -> list[Machine]:
    return [
        Machine(id="RoboticCell", name="cell3", capabilities=["assemble"]),
        Machine(id="QualityCell", name="cell4", capabilities=["quality_check"]),
        Machine(id="Milling", name="cell2", capabilities=["mill"]),
        Machine(id="Warehouse", name="cell5", capabilities=["store"]),
    ]

def _gen_scheduling_instance(num_jobs: int) -> SchedulingInstance:
    jobs: list[Job] = []

    for i in range(num_jobs):
        jobs.append(gen_wh_job())
        jobs.append(gen_qc_job())
        jobs.append(gen_rbtc_job())
        jobs.append(gen_mill_job())
    machines = _gen_machines()

    return SchedulingInstance(jobs=jobs, machines=machines)

def _parse_args():
    parser = argparse.ArgumentParser(description="Generate scheduling instance for pallet selection benchmark.")
    parser.add_argument("--output", type=str, required=True, help="Output file path for the generated scheduling instance.")
    parser.add_argument("--num_jobs", type=int, default=5, help="Number of jobs per type to generate.")
    return parser.parse_args()

if __name__ == "__main__":
    args = _parse_args()

    instance = _gen_scheduling_instance(num_jobs=args.num_jobs)
    
    with open(args.output, "w") as f:
        f.write(instance.model_dump_json(indent=2, exclude_defaults=True))

    
