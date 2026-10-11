# NOTICE

## What this repository is

`wikidare` is an **independent project** derived from **DARE** (the Dietrich
Analysis Research Education platform) by Carnegie Mellon University Libraries:

<https://github.com/cmudco/dare-backend> — forked at commit `991dbcd`.

It is **not affiliated with, sponsored by, or endorsed by** Carnegie Mellon
University, the Wikimedia Foundation, or any Wikimedia project. The name
"wikidare" is this project's own; it is not a Wikimedia or CMU product, and no
partnership is implied.

## Licence and marks

The upstream code is licensed under the **GNU Affero General Public License,
version 3**. `LICENSE` carries an additional notice, which this fork reproduces
unmodified, stating that **"DARE" and "SocraticBots" are trademarks of Carnegie
Mellon University** and that the licence **does not grant permission to use the
trade names, trademarks, service marks or product names** of CMU. (This preamble
is also why GitHub reports the licence as `NOASSERTION` rather than detecting
AGPL automatically. It is the standard AGPL copyright-and-notice form.)

The licence and the trademark restriction are separate instruments. Rights under
the software licence do not grant rights to the name or marks, and compliance
with the trademark notice does not modify the licence obligations.

Modifications made in this fork are distributed under the same terms, AGPL-3.0.
See `LICENSE`.

Because this software is offered to users over a network, AGPL section 13
requires that those users be offered the corresponding source. **This public
repository is that offer.**

## Renaming status

Upstream ships `BRAND.md`, which states that the DARE name and visual identity are
governed separately from the software licence and may not be used without
permission. This deployment therefore operates under the name **wikidare**.

A **complete rebranding of user-visible strings is in progress.** Until it is
finished, DARE-branded names may still appear in the source. Those are references
to upstream, retained for functional and attribution reasons; they are not a claim
to those marks.

## What this repository deliberately does not contain

Deployment-specific configuration for the pilot instance — credentials, network
topology, peer configuration, host inventory and operating notes — is kept in a
separate private repository and is not published here.

In particular, material that is subject to third-party rights is never committed
to this repository, including in test fixtures, issues or commit messages. See the
project's deployment notes, which are private.
