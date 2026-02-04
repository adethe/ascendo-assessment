import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


@dataclass
class Company:
    name: str
    source_url: str
    source_hint: str


def _clean_company_name(s: str) -> Optional[str]:
    if not s:
        return None

    s = re.sub(r"\s+", " ", s).strip()

    if s.lower() in {"img", "image"}:
        return None

    if s.endswith(".") or s.endswith(",") or s.endswith(";"):
        return None
    if s.lower().startswith("and "):
        return None
    if len(s.split()) > 7:
        return None

    if "?" in s or "http" in s.lower() or "/" in s:
        return None
    if re.search(r"\b(png|jpg|jpeg|svg|webp|gif)\b", s, flags=re.I):
        return None

    if re.fullmatch(r"[A-Za-z0-9]{20,}", s):
        return None

    if re.match(r"^20\d{2}\s+\d{3,}\b", s):
        return None

    bad_phrases = {
        "logo", "sponsor", "exhibitor", "partner", "attendee", "companies",
        "blog", "quick reads", "boardroom", "agenda", "session",
    }
    if s.lower() in bad_phrases:
        return None

    if len(s) < 2:
        return None

    s = re.sub(r"[\|\-–—:]+$", "", s).strip()

    cta = {
        "see all attendees", "view all attendees", "see all sponsors", "download brochure",
        "register", "learn more", "contact", "book a meeting",
    }
    if s.lower() in cta:
        return None

    if re.search(r"\b20\d{2}\b", s) and any(
        k in s.lower() for k in ["field service", "west", "east", "conference", "summit"]
    ):
        return None

    words = s.split()
    if len(words) == 2 and all(w[:1].isupper() and w[1:].islower() for w in words):
        common_business_second_words = {
            "technologies", "technology", "digital", "consulting", "planning", "solutions",
            "systems", "services", "software", "networks", "group", "global", "medical",
        }
        if words[1].lower() not in common_business_second_words:
            suffixes = {"inc", "llc", "ltd", "corp", "corporation", "company", "co", "gmbh", "plc"}
            if not any(suf in s.lower() for suf in suffixes):
                return None

    return s or None


def _unique_companies(companies: List[Company]) -> List[Company]:
    seen = set()
    out = []
    for c in companies:
        key = c.name.lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _find_sponsor_links(soup: BeautifulSoup, base_url: str) -> List[str]:
    links = set()
    base_netloc = urlparse(base_url).netloc

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if "/sponsors/" not in href:
            continue

        full = urljoin(base_url, href).split("#")[0]
        if urlparse(full).netloc == base_netloc:
            links.add(full)

    return sorted(links)


def _extract_name_from_sponsor_page(soup: BeautifulSoup) -> Optional[str]:
    h1 = soup.find("h1")
    if h1:
        name = h1.get_text(" ", strip=True)
        if name:
            return name

    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title:
            return title.split("|")[0].strip()

    return None


def _extract_from_html(html: str, base_url: str) -> List[Company]:
    soup = BeautifulSoup(html, "lxml")
    companies = []

    for img in soup.find_all("img"):
        alt = _clean_company_name(img.get("alt", "") or "")
        if alt:
            companies.append(Company(name=alt, source_url=base_url, source_hint="img alt"))

    keywords = ["sponsor", "exhibitor", "partner", "attendee", "companies"]
    for header in soup.find_all(["h1", "h2", "h3", "h4"]):
        htxt = (header.get_text(" ", strip=True) or "").lower()
        if any(k in htxt for k in keywords):
            parent = header.parent
            if parent:
                for a in parent.find_all("a"):
                    txt = _clean_company_name(a.get_text(" ", strip=True) or "")
                    if txt:
                        companies.append(
                            Company(
                                name=txt,
                                source_url=base_url,
                                source_hint=f"near heading: {htxt[:30]}",
                            )
                        )

    return _unique_companies(companies)


def fetch_static(url: str, timeout: int = 30) -> Tuple[str, str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36"
        )
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.text, r.url


def fetch_dynamic(url: str, timeout_ms: int = 45000) -> Tuple[str, str]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        page.wait_for_timeout(1000)
        html = page.content()
        final_url = page.url
        browser.close()
    return html, final_url


def scrape_companies(url: str, sponsor_link_cap: int = 250) -> List[Company]:
    html, final_url = fetch_static(url)
    companies = _extract_from_html(html, final_url)

    soup = BeautifulSoup(html, "lxml")
    sponsor_urls = _find_sponsor_links(soup, final_url)

    for su in sponsor_urls[:sponsor_link_cap]:
        try:
            html_s, final_su = fetch_static(su)
            soup_s = BeautifulSoup(html_s, "lxml")

            name = _extract_name_from_sponsor_page(soup_s)
            name = _clean_company_name(name or "")
            if name:
                companies.append(Company(name=name, source_url=final_su, source_hint="sponsor page h1"))
                continue

            for img in soup_s.find_all("img"):
                alt = _clean_company_name(img.get("alt", "") or "")
                if alt:
                    companies.append(Company(name=alt, source_url=final_su, source_hint="sponsor page img alt"))
                    break
        except Exception:
            continue

    companies = _unique_companies(companies)

    try:
        html2, final_url2 = fetch_dynamic(url)
        companies2 = _extract_from_html(html2, final_url2)
        companies.extend(companies2)
        companies = _unique_companies(companies)
    except Exception:
        pass

    return companies
