import os

import pywikibot


def save_to_wiki_or_local(page, summary, content, minor=True):
    """
    Save the content to the page on a given site or store it locally.

    Whether the pages are outputted locally (and where to) is controlled by the
    LOCAL_WRITE_PATH environment variable.

    @param page: the pywikibot.Page to which the content should be written
    @param content: the content to store
    @param summary: the edit summary to save the content with
    @param minor: if the edit should be marked as minor (defaults to True)
    """
    if not isinstance(page, pywikibot.Page):
        pywikibot.warning(
            "Could not save page {0} because it is not a Page " "instance.".format(page)
        )

    local_path = os.environ.get("LOCAL_WRITE_PATH")

    if not local_path:
        try:
            page.put(newtext=content, summary=summary, minor=minor)
        except (pywikibot.OtherPageSaveError, pywikibot.PageSaveRelatedError):
            pywikibot.warning("Could not save page {0} ({1})".format(page, summary))
    else:
        filename = os.path.join(
            bytes(local_path, encoding="utf-8"), page_to_filename(page)
        )
        with open(filename, "w", encoding="utf-8") as f:
            f.write("#summary: {0}\n---------------\n".format(summary))
            f.write(content)


def page_to_filename(page):
    """
    Create a standardised filename for a page.

    The name takes the form [site][namespace]pagename.wiki where '/', ':' and
    " " has been replaced by '_'. Namespace 0 is given as just '_'.

    @param page: the pywikibot.Page for which to generate a filename.
    """
    namespace_str = page.namespace().custom_prefix().rstrip(":") or "_"
    pagename_str = page.title(as_filename=True, with_ns=False)
    filename = "[{site}][{ns}]{page}.wiki".format(
        site=page.site, ns=namespace_str, page=pagename_str
    )
    return filename.replace(" ", "_").replace(":", "_").encode("utf-8")
