# 04: Reconcile stale Pending transactions on sync

**What to build:** Phantom Pending transactions stop accumulating. A hold that
disappears at the bank disappears here, and a Pending transaction that later
books does not leave a twin behind to be counted a second time. The owner sees a
transactions list and a review queue that shed clutter they never created.

This has to land before Pending spend counts toward anything, or the first
re-sync can double-count a single purchase.

**Blocked by:** 03

**Status:** ready-for-agent

- [ ] After a fully successful Pending fetch for an account, Pending rows inside the fetched window whose provider identifier was absent from the response are deleted
- [ ] A Pending row still present in the response survives untouched
- [ ] A Pending transaction that books under a different provider identifier leaves no twin behind
- [ ] A fetch that fails partway through any page sweeps nothing
- [ ] A Pending row the owner marked Ignored is never swept
- [ ] Both payload shapes are covered: a stable provider transaction identifier present, and absent so the fallback hash is used
- [ ] The Ignored flag is not reused as a marker for swept rows
