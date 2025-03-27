# Using repo and Gerrit for the NDK

Android uses [repo](https://source.android.com/setup/develop#repo) for managing
the collections of individual git repositories needed by each "tree". See that
page for more information, including install instructions. You'll need to
install repo before you can work with Android repositories.

## Downloading the source

AOSP's [Downloading the source] explains how to initialize a new tree (similar
to `git clone`, but for a whole repo tree). For the NDK the main difference is
that you need to specify the master-ndk branch by adding `-b master-ndk`. See
[Building.md](Building.md) for more specific instructions.

Warning: Unlike `git clone`, `repo init` will **not** check out the source into
a new directory. If you run `repo init && repo sync` in your home directory you
will have a lot to clean up. If you run `repo init` in a tree that already has a
different repo tree in it, you'll reinitialize that tree with a different branch
and the next sync may delete existing projects.

`repo init` only prepares the tree, you'll still need to run `repo sync` to
fetch the source.

[Downloading the source]: https://source.android.com/setup/build/downloading

## Pulling updates

The `repo` equivalent of `git pull` is `repo sync`. It's recommended that you
run `repo sync -c -j $THREADS`. `-c` ensures that only the branches that are
needed are fetched to avoid consuming too much disk space, and `-j $THREADS`
allows repo to use multiple threads when updating.

## Making changes

`repo` trees place git projects in a detached HEAD state by default. To create a
local branch that can be sent for review, use `repo start $BRANCH_NAME .`. This
is similar to `git checkout -b` or `git switch -c`, but will configure the new
branch so that it can be uploaded for review.

Any time you start new work, use `repo start $BRANCH_NAME .`. Each local branch
is its own review chain, so you'll want separate branches for distinct changes.

## Committing changes

When you're ready to upload your changes, commit them to your local branch.
Gerrit will create one review per commit and will associate commits that are in
the same branch together in a series. If you made many commits while working on
the change, squash them (`repo rebase -i --autosquash .` will start an
interactive rebase that you can use to re-order and combine commits) so that
each commit is complete but minimal. Splitting large changes into multiple
commits improves reviewability, but each commit should be able to build and pass
tests on its own so it can be submitted individually.

In most cases you'll only need one commit in a branch.

## Uploading changes for review

To get changes reviewed, run `repo upload --cbr .`. This will upload the commits
in the current branch and directory. To upload changes in other directories,
pass those paths instead of `.`. Multiple paths can be given to upload multiple
projects with the same command.`--cbr` is "current branch". Without `--cbr` an
interactive mode will open in your editor that you can use to upload branches
other than the one that is currently checked out.

You can also add reviewers when uploading your changes with the
`--re=$USER1,$USER2,...` argument. If your reviewers are Googlers, Gerrit can
*usually* work out that `name` means `name@google.com`. In other cases you'll
need to spell out the full email address of the reviewer.

Once the change is uploaded, you can open it in Gerrit and enable autosubmit if
you want the change to be submitted once it has been reviewed and passed
presubmit testing. Don't worry, if anyone has review comments those will prevent
the change from being submitted before you can see them.

To minimize the amount of time you spend waiting on machines, it's best to vote
Presubmit Ready+1 on your change when you upload it to get treehugger running
ASAP. By default treehugger won't start testing a change until it has either
been +2'd or has autosubmit set.

If you have changes that span multiple git projects that need to be submitted
together (are mutually dependent), give them the same topic name in Gerrit. If
you used the same branch name when running `repo start` in each project, you can
pass `-t` to `repo upload` to automatically assign the branch name as the topic
name in Gerrit.

## Responding to review comments

To update your commit to address review comments, make the change and amend the
commit. If you have a stack of commits and need to amend something other than
the top commit, you can use the `--fixup` argument to `git commit` and then
rebase with `--autosquash`, or use the `edit` option on a commit after starting
an interactive rebase (`repo rebase -i --autosquash .`).

After amending your changes, run `repo upload` again as you did before. This
will create a new "patch set" (PS) for the existing review in Gerrit. This is a
new "version" of the commit. You do not need to specify reviewers again when
uploading new patch sets.

## Submitting

Once you have approval (Code Review +2) and either a +1 or a +2 from someone in
the OWNERS file (or are in the OWNERS file yourself), all review comments have
been addressed and marked as "Done", and presubmit (AKA "treehugger") has
responded with Presubmit Verified +1, your change can be submitted. If you
enabled autosubmit this will happen automatically. Otherwise use the "Submit"
button in the UI.

## Cheat sheet for GitHub users

The repo/Gerrit process has some differences compared to the GitHub Pull Request
workflow. If you're familiar with using pull requests you should read everything
above for the details, but here's a quick cheat sheet mapping similar processes:

GitHub | Gerrit
--- | ---
`git clone $X` | `mkdir $X && cd $X && repo init $X && repo sync`
`git pull` | `repo sync`
`git checkout -b`/`git switch -c` | `repo start .`
`git push` and other pull request steps | `repo upload`
