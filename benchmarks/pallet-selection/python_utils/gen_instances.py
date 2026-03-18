import argparse
import uuid

from frost_planner.core.base import Job, Machine, SchedulingInstance, Task


def _gen_job(
    job_name: str, task_name: str, requires: list[str], processing_time=45, priority=1
) -> Job:
    assert requires, "Requires list cannot be empty"
    task = Task(
        id=str(uuid.uuid4()),
        name=task_name,
        processing_time=processing_time,
        requires=requires,
        priority=priority,
    )
    return Job(
        id=str(uuid.uuid4()),
        name=job_name,
        priority=priority,
        tasks=[
            task,
            # gen_wait_task(requires=requires, dependencies=[task.id])
        ],
    )


def gen_wait_task(requires: list[str], dependencies: list[str]) -> Task:
    return Task(
        id=str(uuid.uuid4()),
        name="WaitPalletAtSegment",
        processing_time=10,
        requires=requires,
        priority=1,
        dependencies=dependencies,
    )


def gen_wh_job() -> Job:
    return _gen_job(
        job_name="ToWarehouseAndBack",
        task_name="ToWarehouseAndBack",
        requires=["store"],
        processing_time=45,
        priority=1,
    )


def gen_qc_job() -> Job:
    return _gen_job(
        job_name="ToQcAndBack",
        task_name="ToQcAndBack",
        requires=["quality_check"],
        processing_time=45,
        priority=1,
    )


def gen_rbtc_job() -> Job:
    return _gen_job(
        job_name="ToRbtcAndBack",
        task_name="ToRbtcAndBack",
        requires=["assemble"],
        processing_time=45,
        priority=1,
    )


def gen_mill_job() -> Job:
    return _gen_job(
        job_name="ToMillAndBack",
        task_name="ToMillAndBack",
        requires=["mill"],
        processing_time=45,
        priority=1,
    )


def gen_lego_movements_job() -> Job:
    """Generate a movements-only lego job: RBTC → QC → DISASSEMBLE → PUT_BACK (no LD/RESERVE)."""
    rbtc = Task(id=str(uuid.uuid4()), name="RBTC", processing_time=15, requires=["assemble"], priority=1)
    qc = Task(id=str(uuid.uuid4()), name="QC", processing_time=25, requires=["quality_check"], priority=1, dependencies=[rbtc.id])
    disassemble = Task(id=str(uuid.uuid4()), name="DISASSEMBLE", processing_time=45, requires=["disassemble"], priority=1, dependencies=[qc.id])
    put_back = Task(id=str(uuid.uuid4()), name="PUT_BACK", processing_time=45, requires=["disassemble"], priority=1, dependencies=[disassemble.id])
    return Job(
        id=str(uuid.uuid4()),
        name="LegoMovementsRecipe",
        priority=1,
        tasks=[rbtc, qc, disassemble, put_back],
    )

def gen_lego_job_no_reserve() -> Job:
    """Generate a full lego job: LD → RBTC → QC → DISASSEMBLE →  PUT_BACK."""
    ld = Task(id=str(uuid.uuid4()), name="LD", processing_time=60, requires=["reserve_pallet"], priority=1)
    rbtc = Task(id=str(uuid.uuid4()), name="RBTC", processing_time=45, requires=["assemble"], priority=1, dependencies=[ld.id])
    qc = Task(id=str(uuid.uuid4()), name="QC", processing_time=30, requires=["quality_check"], priority=1, dependencies=[rbtc.id])
    disassemble = Task(id=str(uuid.uuid4()), name="DISASSEMBLE", processing_time=60, requires=["disassemble"], priority=1, dependencies=[qc.id])
    put_back = Task(id=str(uuid.uuid4()), name="PUT_BACK", processing_time=30, requires=["disassemble"], priority=1, dependencies=[disassemble.id])
    return Job(
        id=str(uuid.uuid4()),
        name="LegoRecipe",
        priority=1,
        tasks=[ld, rbtc, qc, disassemble, put_back],
    )


def gen_lego_job() -> Job:
    """Generate a full lego job: LD → RBTC → QC → DISASSEMBLE → RESERVE → PUT_BACK."""
    ld = Task(id=str(uuid.uuid4()), name="LD", processing_time=60, requires=["reserve_pallet"], priority=1)
    rbtc = Task(id=str(uuid.uuid4()), name="RBTC", processing_time=45, requires=["assemble"], priority=1, dependencies=[ld.id])
    qc = Task(id=str(uuid.uuid4()), name="QC", processing_time=30, requires=["quality_check"], priority=1, dependencies=[rbtc.id])
    disassemble = Task(id=str(uuid.uuid4()), name="DISASSEMBLE", processing_time=60, requires=["disassemble"], priority=1, dependencies=[qc.id])
    reserve = Task(id=str(uuid.uuid4()), name="RESERVE", processing_time=60, requires=["reserve_pallet"], priority=1, dependencies=[disassemble.id])
    put_back = Task(id=str(uuid.uuid4()), name="PUT_BACK", processing_time=30, requires=["disassemble"], priority=1, dependencies=[disassemble.id, reserve.id])
    return Job(
        id=str(uuid.uuid4()),
        name="LegoRecipe",
        priority=1,
        tasks=[ld, rbtc, qc, disassemble, reserve, put_back],
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

    for _ in range(num_jobs):
        jobs.append(gen_wh_job())
        jobs.append(gen_qc_job())
        jobs.append(gen_rbtc_job())
        jobs.append(gen_mill_job())
    machines = _gen_machines()

    return SchedulingInstance(jobs=jobs, machines=machines)


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Generate scheduling instance for pallet selection benchmark."
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output file path for the generated scheduling instance.",
    )
    parser.add_argument(
        "--num_jobs", type=int, default=5, help="Number of jobs per type to generate."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    instance = _gen_scheduling_instance(num_jobs=args.num_jobs)

    with open(args.output, "w") as f:
        f.write(instance.model_dump_json(indent=2, exclude_defaults=True))
