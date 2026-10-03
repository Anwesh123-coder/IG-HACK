import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urlunparse
import re
import concurrent.futures
import time
import sys
from collections import deque

class DBRecon:
    def __init__(self, base_url, max_depth=3, timeout=5):
        # Normalize URL
        if not base_url.startswith(('http://', 'https://')):
            base_url = 'http://' + base_url
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.max_depth = max_depth
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'DBRecon/1.0 (Security Auditor)'})
        
        # Storage
        self.visited = set()
        self.links = set()
        self.findings = {
            "exposed_files": [],
            "connection_strings": [],
            "sql_errors": [],
            "tech_stack": [],
            "api_endpoints": [],
            "sensitive_headers": []
        }
        
        # Patterns for detection
        self.db_patterns = {
            "connection_strings": [
                r'(mongodb(\+srv)?://[^\s"\']+)',
                r'(mysql://[^\s"\']+)',
                r'(postgres(?:ql)?://[^\s"\']+)',
                r'(jdbc:[^\s"\']+)',
                r'(sqlite(?:3)?://[^\s"\']+)'
            ],
            "sql_errors": [
                r'(syntax error at or near\s*["\']?[\w"\']+)',
                r'(unknown column\s*["\']?[\w"\']+)',
                r'(relation\s*["\']?[\w"\']+?\s*does not exist)',
                r'(table\s*["\']?[\w"\']+?\s*doesn\'t exist)',
                r'(SQLSTATE:\s*\[?[\dA-Z\[\]\s\]\]*\])',
                r'(Warning:\s*(?:mysql|mysqli|pg_)\w+\s*\()'
            ],
            "sensitive_files": [
                r'(\.env(\.[\w]+)?)$',
                r'(\.git(config|ignore)?)$',
                r'(\.sql(\.gz|\.zip)?)$',
                r'(\.sqlite(\.\d)?(\.db)?)$',
                r'(\.bak|\.old|\.backup)$',
                r'(\.log)$',
                r'(/phpmyadmin)',
                r'(/adminer)',
                r'(/wp-content/database)',
                r'(/config/)',
                r'(/\.htaccess)',
                r'(/\.DS_Store)'
            ],
            "tech_stack": [
                (r'laravel', 'Laravel'),
                (r'django', 'Django'),
                (r'rails|ruby', 'Ruby on Rails'),
                (r'express\.js|node\.js', 'Node.js/Express'),
                (r'asp\.net', 'ASP.NET'),
                (r'php', 'PHP')
            ]
        }

    def is_same_domain(self, url):
        parsed = urlparse(url)
        return parsed.netloc == self.domain or parsed.netloc.endswith('.' + self.domain)

    def sanitize_url(self, url):
        # Remove fragments and normalize
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, parsed.query, ''))

    def fetch(self, url):
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            return response
        except requests.exceptions.RequestException:
            return None

    def analyze_content(self, url, content, content_type=""):
        """Scans content for sensitive patterns."""
        if not content:
            return

        # 1. Connection Strings
        for pattern in self.db_patterns["connection_strings"]:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match not in self.findings["connection_strings"]:
                    self.findings["connection_strings"].append(match)
                    print(f"[+] Connection String Found: {match}")

        # 2. SQL Errors
        for pattern in self.db_patterns["sql_errors"]:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                if match not in self.findings["sql_errors"]:
                    self.findings["sql_errors"].append(match)
                    print(f"[!] SQL Error/Leak Detected: {match}")

        # 3. Tech Stack
        for pattern, tech in self.db_patterns["tech_stack"]:
            if re.search(pattern, content, re.IGNORECASE):
                if tech not in self.findings["tech_stack"]:
                    self.findings["tech_stack"].append(tech)

        # 4. Sensitive File Names in URL or Content
        for pattern in self.db_patterns["sensitive_files"]:
            if re.search(pattern, url, re.IGNORECASE):
                if url not in self.findings["exposed_files"]:
                    self.findings["exposed_files"].append(url)
                    print(f"[+] Exposed Sensitive Path: {url}")

    def extract_links(self, url, soup):
        """Extracts internal links from HTML."""
        for tag in soup.find_all(['a', 'link', 'script'], href=True):
            link = urljoin(url, tag['href'])
            link = self.sanitize_url(link)
            if self.is_same_domain(link) and link not in self.visited:
                self.links.add(link)

    def crawl(self):
        """BFS Crawler to discover endpoints."""
        queue = deque([(self.base_url, 0)])
        self.visited.add(self.base_url)
        
        print(f"[*] Starting crawl of {self.base_url} (Max Depth: {self.max_depth})")
        
        while queue:
            current_url, depth = queue.popleft()
            print(f"[*] Crawling: {current_url} (Depth: {depth})")
            
            response = self.fetch(current_url)
            if not response:
                continue

            # Analyze headers
            for header, value in response.headers.items():
                if header.lower() in ['x-powered-by', 'server', 'x-aspnet-version']:
                    self.findings["sensitive_headers"].append(f"{header}: {value}")

            # Analyze content
            content_type = response.headers.get('Content-Type', '')
            text = response.text
            self.analyze_content(current_url, text, content_type)

            # If HTML, extract links
            if 'html' in content_type and depth < self.max_depth:
                soup = BeautifulSoup(text, 'html.parser')
                new_links = []
                for tag in soup.find_all(['a', 'link', 'script', 'iframe'], href=True):
                    link = urljoin(current_url, tag['href'])
                    link = self.sanitize_url(link)
                    if self.is_same_domain(link) and link not in self.visited:
                        new_links.append(link)
                
                for link in new_links:
                    self.visited.add(link)
                    queue.append((link, depth + 1))

    def fuzz_database_artifacts(self):
        """Actively probes for common database file locations."""
        print("[*] Fuzzing for common database artifacts...")
        common_paths = [
            "/.env", "/.env.local", "/.env.production",
            "/database.yml", "/config/database.yml",
            "/db.sqlite3", "/db.sqlite", "/database.db",
            "/dump.sql", "/db.sql", "/backup.sql",
            "/phpmyadmin/index.php", "/adminer.php",
            "/wp-content/database/", "/wp-json/wp/v2/",
            "/api/", "/graphql",
            "/.git/config", "/.git/HEAD",
            "/server-status", "/server-info"
        ]
        
        base = self.base_url.rstrip('/')
        urls_to_check = [f"{base}{path}" for path in common_paths]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(self.fetch, url): url for url in urls_to_check}
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    response = future.result()
                    if response and response.status_code == 200:
                        # Check if it's actually a sensitive file
                        content = response.text
                        is_sensitive = any(re.search(p, url, re.IGNORECASE) for p in self.db_patterns["sensitive_files"])
                        
                        # Heuristic: If it's JSON and looks like config, flag it
                        if 'json' in response.headers.get('Content-Type', ''):
                            if any(key in content.lower() for key in ['db', 'database', 'host', 'port', 'password']):
                                is_sensitive = True
                                
                        if is_sensitive:
                            if url not in self.findings["exposed_files"]:
                                self.findings["exposed_files"].append(url)
                                print(f"[!] FOUND SENSITIVE ENDPOINT: {url} (Status: {response.status_code})")
                except Exception as e:
                    pass

    def generate_report(self):
        print("\n" + "="*60)
        print("       DATABASE RECONNAISSANCE REPORT")
        print("="*60)
        print(f"Target: {self.base_url}")
        print(f"Pages Crawled: {len(self.visited)}")
        print(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("-"*60)

        if self.findings["exposed_files"]:
            print("\n[CRITICAL] Exposed Sensitive Files/Paths:")
            for f in self.findings["exposed_files"]:
                print(f"  - {f}")

        if self.findings["connection_strings"]:
            print("\n[HIGH] Database Connection Strings Found:")
            for c in self.findings["connection_strings"]:
                print(f"  - {c}")

        if self.findings["sql_errors"]:
            print("\n[MEDIUM] SQL Error Messages (Schema Leakage):")
            for e in self.findings["sql_errors"][:10]: # Limit output
                print(f"  - {e}")

        if self.findings["tech_stack"]:
            print("\n[INFO] Detected Tech Stack:")
            for t in self.findings["tech_stack"]:
                print(f"  - {t}")

        if self.findings["sensitive_headers"]:
            print("\n[INFO] Server Headers:")
            for h in self.findings["sensitive_headers"]:
                print(f"  - {h}")

        if not any(self.findings.values()):
            print("\n[OK] No obvious database artifacts or leaks found in top-level crawl.")
            print("Note: Deep API fuzzing or authenticated crawling may be required for deeper analysis.")
        
        print("="*60)

    def run(self):
        self.crawl()
        self.fuzz_database_artifacts()
        self.generate_report()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="DBRecon: Website Database Fingerprinting Tool")
    parser.add_argument("url", help="Target website URL (e.g., example.com)")
    parser.add_argument("-d", "--depth", type=int, default=3, help="Max crawl depth (default: 3)")
    
    args = parser.parse_args()
    
    # Run the auditor
    auditor = DBRecon(args.url, max_depth=args.depth)
    auditor.run()
