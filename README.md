# .github

### Actions

Each time a new commit is pushed, re-create the branch `v1` on the GitHub repository so that the updated actions will be used by dependent repositories. 

As an example:

https://github.com/flowscripter/template-deno-library/blob/main/.github/workflows/release-deno-library.yml

refers to the `release-deno-library` action in this repository as:

`flowscripter/.github/actions/release-deno-library@v1`
