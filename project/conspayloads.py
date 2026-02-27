# consolidation-payloads.py

def build_consolidation_payload(
    book_name: str,
    period: str,
    email: str = "girish.dhareshwar@sage.com",
    run_offline: bool = False,
    update_net_changes: bool = False,
    update_subsequent_periods: bool = False
) -> dict:
    """
    Build Intacct consolidation payload.
    """

    return {
        "consolidationBook": {
            "id": book_name
        },
        "timePeriod": {
            "id": period
        },
        "notificationEmail": email,
        "runOffline": run_offline,
        "updateNetChanges": update_net_changes,
        "updateSubsequentPeriods": update_subsequent_periods
    }