# Problem

The brief for this build, in Michael's words (2026-11-13), in the order given.

> open discord and navigate to the dsh forge channel. use your most efficient method to extract all the discussion inside that channel as well as my dms with the other active member to determine the plan for this app. grill me continuously until all ambiguities are cleared up and i agree on the shape of the plan then make your plan before awaiting my green light to execute. make sure the codebase is up to date with most recent version.

> as you build this do so with /kickoff and make sure you fix existing code to integrate it with this and make sure you make changes atomically with tests and ensure everything works when u ship new features and test full functionality for major releases, iteratively testing and fixing everything until it all works and continue going on and on make sure to test this directly with computer use and do the entire thing autonomously running for hours if needed until the entire thing is done

> make sure to build the actual hidden gem detection system, dont overuse my ai subscription so do it on a tiny subset of the community contributions as needed. this is key to the app so make sure you continuosuly optimize and evaluate the results for this feature, and make sure the system is relatively seperated from the app itself so it can be worked on in seperate

On who reads the code in the hidden-gem deep stage:

> just do it over a decent amount for now to populate the recommended with some genuinely good stuff and we'll build it out but actually plugin the sub later

## What the team discussion asked for

Condensed from the project's Discord server and direct messages, September to October 2026. These are the recurring product requirements, not a transcript.

- Make it easy to discover, find and boot your favourite DSH profiles.
- Focus on discoverability of hidden gems and the ability to save and run your own and community configurations, rather than on "the forge".
- Hidden-gem discovery should be the best part of the product, and should genuinely analyse projects rather than only asking an AI.
- Featured shelves that update constantly: most liked in the community, new, best in class for the main feature a project provides, and hidden gems.
- Thumbnails and metadata tags for as many plugins and forks as possible; better search, sort and filter.
- A much smoother interface with the technical detail taken out, and no greyed-out unimplemented features.
- Keep existing plugins and forks up to date by checking for changes.
- Act as a layer around every harness version the user runs: analyse their session logs and recommend plugins to try, shown on the launcher page.
- Make it easy to run any task through any saved harness configuration, including several in parallel, each with its own configuration.
- An MCP server and an embedded harness tab that helps with discovery and merging.
- Sign-in with GitHub, likes and favourites.
- A new name (the current one is taken), production and preview deployments, and a public launch with posts.
- Later, once there is a community: crowdsourced compute and feedback, and the project's own base harness versions that build and publish packs.
