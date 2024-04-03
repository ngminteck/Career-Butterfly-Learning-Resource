import spacy
import pandas as pd
import pypandoc
import csv
import os
import glob
from os import listdir
from os.path import isfile, join
import shutil
import zipfile
import html2text
import json
import re
from flask import Flask, send_file, request,jsonify
from spacy.matcher import PhraseMatcher
from skillNer.general_params import SKILL_DB
from skillNer.skill_extractor_class import SkillExtractor
from werkzeug.serving import run_simple
from waitress import serve

"""
Sorry did not follow in python, all method also lower case.
"""

"""
Skill class are basically just a custom type to wrap all the data info
"""


class Skill:

    def __init__(self, name, keyword, groups=None):
        filename = name
        filename = filename.replace('/', '-')
        filename = filename.replace("\\", '-')
        filename = filename + ".html"
        path = os.path.join("skill", filename)
        path = path.replace("\\", '/')
        self.resource_path = path  # for the resource path
        self.keyword_search = keyword  # keyword for searching LLM
        self.group_set = set()
        if groups is not None:
            self.UpdateGroupSet(groups)

    def UpdateGroupSet(self, groups):
        self.group_set.update(groups)
        # print("skill group set updated.")

    def ChangeKeyword(self, keyword):
        self.keyword_search = keyword


"""
Learning Resource Service as a an object that handle everything about generate learning resource
"""


class LearningResourceService:
    def __init__(self):
        self.nlp = spacy.load('en_core_web_lg')
        self.skill_extractor = SkillExtractor(self.nlp, SKILL_DB, PhraseMatcher)
        self.skill_dict_list = {}
        self.group_dict_list = {}
        self.exact_match_replace_dict_list = {}
        self.partial_match_replace_dict_list = {}
        self.not_found_dict_list = {}
        self.three_word_skill_classification_set = set()
        self.two_word_skill_classification_set = set()
        self.one_word_skill_classification_set = set()
        self.backup_keyword_dict_list = {}
        self.partial_search_ignore_list = ["apache", "microsoft", "google", "amazon", "apple", "vmware", "ibm",
                                           "oracle", "sap"]
        self.leetcode_list = ["c++", "c", "c#", "python", "java", "javascript", "typescript", "php", "swift", "kotlin",
                              "go", "ruby", "scala", "rust", "racket"]
        self.one_keyword_dict_list = {}
        self.two_keyword_dict_list = {}
        self.three_keyword_dict_list = {}
        self.leetcode_company_dict_list = {}
        self.leetcode_overall_frequency_dict_list = {}
        self.AllThisWillBeRemoveOnceFinalize()
        self.ImportClassificationSet()
        self.ImportSkillDictList()
        self.InitKeywordDictList()
        self.InitLeetCodeCompanyNameDictList()
        self.InitLeetcodeOverallFrequencyDictList()
        self.request_queue_no = 0

    """
    Take in any number of string,
    lower case all word and keep only 1 space in between the word,
    remove all the symbol,
    except, dash which keep only if in between 2 word, 
    dot if in between 2 word and if . is the first character of the word
    """

    @staticmethod
    def WordPreprocessing(string_text):
        string_text = string_text.replace("[", "")
        string_text = string_text.replace("]", "")
        string_text = string_text.replace("(", "")
        string_text = string_text.replace(")", "")
        string_text = string_text.replace(":", "")
        string_text = string_text.replace("*", "")
        string_text = string_text.replace("\\", "")
        string_text = string_text.replace("\"", "")
        string_text = string_text.replace("’s", "")
        string_text = string_text.replace("?", "")
        string_text = string_text.replace("!", "")
        string_text = string_text.replace("&", "")
        string_text = string_text.replace("%", "")
        string_text = string_text.replace("_", "")
        string_text = string_text.replace(",", "")
        string_text = string_text.replace("*", "")
        string_text = string_text.replace("\n", " ")
        string_text = string_text.replace("/", " ")
        string_text = re.sub(r'\s+', ' ', string_text)
        string_text = re.sub(r'\s-\s', ' ', string_text)
        string_text = re.sub(r'\s\.\s', ' ', string_text)
        string_text = string_text.replace(" -", " ")
        string_text = string_text.replace("- ", " ")
        string_text = string_text.replace(". ", " ")
        string_text = string_text.lower()
        return string_text

    """
    Convert HTML to text format, remove all image, link and rich text format
    """

    def ConvertHtmlToString(self, html_text):
        h = html2text.HTML2Text()
        h.ignore_images = True
        h.ignore_links = False
        h.inline_links = True
        h.reference_links = False
        string_text = h.handle(html_text)
        string_text = re.sub(r'https://\S+', '', string_text)
        string_text = re.sub(r'[^\x00-\x7F]+', '', string_text)
        string_text = re.sub(r'\[\d+]\s*', '', string_text)
        string_text = self.WordPreprocessing(string_text)
        return string_text

    """
    Convert HTML to text format, keep all image and link, but remove rich text format
    """

    @staticmethod
    def ConvertHtmlToString2(html_text):
        h = html2text.HTML2Text()
        h.ignore_images = True
        h.ignore_links = False
        h.inline_links = False
        h.reference_links = False
        string_text = h.handle(html_text)
        string_text = re.sub(r'[^\x00-\x7F]+', '', string_text)
        string_text = re.sub(r'\[\d+]\s*', '', string_text)
        string_text = string_text.replace("**", "")
        return string_text

    """
    Below method just how construct the skill dict list, import & export data
    """

    def AddSkillDictList(self, name, keyword, groups=None):
        if name not in self.skill_dict_list:
            self.skill_dict_list[name] = Skill(name, keyword, groups)
            if groups is not None:
                for g in groups:
                    if g in self.group_dict_list:
                        self.group_dict_list.get(g).add(name)
                    else:
                        new_set = set()
                        new_set.add(name)
                        self.group_dict_list[g] = new_set

        else:
            self.skill_dict_list[name].UpdateGroupSet(groups)

    def ReClassificationSkillDictList(self, name, keyword, groups):
        search_keyword = keyword
        if name in self.backup_keyword_dict_list:
            search_keyword = self.backup_keyword_dict_list[name]
        self.AddSkillDictList(name, search_keyword, groups)

    def ImportClassificationSet(self):
        file = open("word classification/classification words.txt", "r")
        for word in file:
            word = word.replace("\n", "")
            word_list = word.split()
            if len(word_list) == 1:
                self.one_word_skill_classification_set.add(word)
            elif len(word_list) == 2:
                self.two_word_skill_classification_set.add(word)
            else:
                self.three_word_skill_classification_set.add(word)
        file.close()

    def ExportSkillDictList(self):
        file_path = "skills.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Search Keyword", "Resource Path", "Groups"])
            for key, value in self.skill_dict_list.items():
                name = key
                search = value.keyword_search
                path = value.resource_path
                groups = ""

                for g in value.group_set:
                    groups += "["
                    groups += g
                    groups += "]"

                writer.writerow([name, search, path, groups])
            file.close()
        with open('skills.txt', 'w') as f:
            for i in self.skill_dict_list:
                f.write(i)
                f.write("\n")
            f.close()

    def ImportSkillDictList(self):
        df = pd.read_csv("skills.csv")
        for index, row in df.iterrows():
            name = str(row['Name'])
            keyword = str(row['Search Keyword'])
            groups = str(row['Groups'])
            groups_set = None
            groups = groups.replace('[', '')
            groups_list = groups.split(']')
            if len(groups_list) > 0:
                groups_list = groups_list[:-1]
                groups_set = set()
                for g in groups_list:
                    groups_set.add(g)
            # auto create group also
            self.AddSkillDictList(name, keyword, groups_set)

    def ExportGroupDictList(self):
        file_path = "groups.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "skills"])
            for key, value in self.group_dict_list.items():
                name = key
                skills = ""
                for s in value:
                    skills += "["
                    skills += s
                    skills += "]"
                writer.writerow([name, skills])
            file.close()

    def ExportNotFoundSet(self):
        file_path = "not found.csv"
        with open(file_path, 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Name", "Search Keyword", "Resource Path"])
            for key, value in self.not_found_dict_list.items():
                name = key
                search = value.keyword_search
                path = "skill unclassified/not tech/" + name + ".html"

                writer.writerow([name, search, path])
            file.close()

    def InitKeywordDictList(self):
        self.one_keyword_dict_list.clear()
        self.two_keyword_dict_list.clear()
        self.three_keyword_dict_list.clear()
        for s in self.skill_dict_list:
            words = s.split()
            if len(words) == 1:
                self.one_keyword_dict_list[s] = s
            elif len(words) == 2:
                self.two_keyword_dict_list[s] = s
            else:
                self.three_keyword_dict_list[s] = s

    def InitLeetCodeCompanyNameDictList(self):
        f = open("leetcode/companies.txt", "r")

        for c in f:
            c = c.replace("\n", "")
            key = c
            key = key.lower()
            self.leetcode_company_dict_list[key] = c
        f.close()

    def InitLeetcodeOverallFrequencyDictList(self):
        df = pd.read_csv("leetcode/Question List.csv")
        for index, row in df.iterrows():
            self.leetcode_overall_frequency_dict_list[str(row["No"])] = str(row["Frequency"])

    def AllThisWillBeRemoveOnceFinalize(self):

        self.exact_match_replace_dict_list["tdd"] = "testing"
        self.exact_match_replace_dict_list["webdriver"] = "web crawler"
        self.exact_match_replace_dict_list["vbnet"] = "visual basic .net"
        self.exact_match_replace_dict_list["vb.net"] = "visual basic .net"
        self.exact_match_replace_dict_list["vb"] = "visual basic"
        self.exact_match_replace_dict_list["html5"] = "html"
        self.exact_match_replace_dict_list["svn"] = "subversion"
        self.exact_match_replace_dict_list["unity3d"] = "unity"
        self.exact_match_replace_dict_list["mssql"] = "microsoft sql"
        self.exact_match_replace_dict_list["shaders"] = "shader"
        self.exact_match_replace_dict_list["uat"] = "testing"
        self.exact_match_replace_dict_list["mui"] = "material ui"
        self.exact_match_replace_dict_list["gui"] = "graphical user interface"
        self.exact_match_replace_dict_list["ui"] = "user interface"
        self.exact_match_replace_dict_list["aliyun"] = "alibaba cloud"
        self.exact_match_replace_dict_list["ali-cloud"] = "alibaba cloud"
        self.exact_match_replace_dict_list["asp.net mvc 5"] = "asp.net mvc"

        self.partial_match_replace_dict_list["ms"] = "microsoft"
        self.partial_match_replace_dict_list["db"] = "database"

    """
    not in use, this for if handle more than 1 request
    """

    def GetRequestQueueNo(self):
        # self.request_queue_no += 1
        return self.request_queue_no

    """
    This function for finding all technical term keyword from all skill the learning resource, 
    so that we can group those skill by relation.
    """

    def FindClassificationKeyword(self):
        directory = 'skill'
        filenames = [f for f in listdir(directory) if isfile(join(directory, f))]
        skillNer_dict_list = {}

        for f in filenames:
            words = f.rsplit(".")
            extension = words[len(words) - 1]
            if extension == "html":
                print(f)
                with open(directory + "/" + f, 'r', encoding="utf-8") as file:
                    html_content = file.read()
                    file.close()
                string_text = self.ConvertHtmlToString(html_content)

                try:
                    annotations = self.skill_extractor.annotate(string_text)
                    # self.skill_extractor.describe(annotations)
                    result = annotations["results"]
                    skill_list_1 = result["full_matches"]
                    skill_list_2 = result["ngram_scored"]

                    for i in range(len(skill_list_1)):
                        info = skill_list_1[i]
                        skill = info["doc_node_value"]
                        skill = skill.lower()
                        if skill not in skillNer_dict_list:
                            skillNer_dict_list[skill] = 0
                        skillNer_dict_list[skill] += 1
                    for i in range(len(skill_list_2)):
                        info = skill_list_2[i]
                        skill = info["doc_node_value"]
                        skill = skill.lower()
                        if skill not in skillNer_dict_list:
                            skillNer_dict_list[skill] = 0
                        skillNer_dict_list[skill] += 1
                except:
                    print(f, "error.")

        with open('word classification/skillNer word.txt', 'w', encoding="utf-8") as f:
            for s in sorted(skillNer_dict_list, key=skillNer_dict_list.get, reverse=True):
                f.write(str(s) + " - " + str(skillNer_dict_list[s]))
                f.write('\n')
            file.close()

    """
    This function for classified all skill in the relation keyword.
    """

    def SkillReClassification(self):
        self.backup_keyword_dict_list.clear()
        for s in self.skill_dict_list:
            self.backup_keyword_dict_list[s] = self.skill_dict_list[s].keyword_search
        self.skill_dict_list.clear()
        self.group_dict_list.clear()
        directory = 'skill'
        filenames = [f for f in listdir(directory) if isfile(join(directory, f))]

        for f in filenames:
            words = f.rsplit(".")
            extension = words[len(words) - 1]
            if extension == "html":
                print(f)
                filename = f.replace(".html", "")
                with open(directory + "/" + f, 'r', encoding="utf-8") as file:
                    html_content = file.read()
                    file.close()
                text_content = self.ConvertHtmlToString(html_content)

                words = text_content.split()
                have_classified = False
                for i in range(len(words)):
                    first_word = words[i]
                    if first_word.endswith('.'):
                        first_word = first_word[:-1]

                    one_word = first_word

                    if one_word in self.one_word_skill_classification_set:
                        self.ReClassificationSkillDictList(filename, filename, {one_word})
                        have_classified = True

                    if i + 1 >= len(words):
                        break
                    second_word = words[i + 1]
                    if second_word.endswith('.'):
                        second_word = second_word[:-1]

                    two_word = first_word + " " + second_word

                    if two_word in self.two_word_skill_classification_set:
                        self.ReClassificationSkillDictList(filename, filename, {two_word})
                        have_classified = True

                    if i + 2 >= len(words):
                        break
                    third_word = words[i + 2]
                    if third_word.endswith('.'):
                        third_word = third_word[:-1]
                    three_word = first_word + " " + second_word + " " + third_word
                    if three_word in self.three_word_skill_classification_set:
                        self.ReClassificationSkillDictList(filename, filename, {three_word})
                        have_classified = True

                if not have_classified:
                    self.ReClassificationSkillDictList(filename, filename + " in tech", {"unknown"})

        self.InitKeywordDictList()
        self.ExportSkillDictList()
        self.ExportGroupDictList()

    """
    This function for extract the technical skill in the description.
    Two stages are used to extract the technical skill in the description,
    the first stage are using the existing skill keyword (skill_dict_list) and do the extract matching.
    the second stage is using spacy skillNer model to extract all the hard skill and soft skill are not in the 
    skill_dict_list
    """

    def ExtractSkillKeyword(self, text):
        skill_set = set()
        text = self.WordPreprocessing(text)
        words = text.split()

        for i in range(2, len(words)):
            search_word = words[i - 2] + " " + words[i - 1] + " " + words[i]
            if search_word in self.three_keyword_dict_list:
                skill_set.add(self.three_keyword_dict_list[search_word])
        for i in range(1, len(words)):
            search_word = words[i - 1] + " " + words[i]
            if search_word in self.two_keyword_dict_list:
                skill_set.add(self.two_keyword_dict_list[search_word])
        for i in range(len(words)):
            if words[i] in self.one_keyword_dict_list:
                skill_set.add(self.one_keyword_dict_list[words[i]])

        try:
            annotations = self.skill_extractor.annotate(text)
            # self.skill_extractor.describe(annotations)
            result = annotations["results"]
            skill_list_1 = result["full_matches"]
            skill_list_2 = result["ngram_scored"]

            for i in range(len(skill_list_1)):
                info = skill_list_1[i]
                skill = info["doc_node_value"]
                skill = skill.lower()
                skill = re.sub(r'\bdatum\b', 'data', skill)
                skill_set.add(skill)
            for i in range(len(skill_list_2)):
                info = skill_list_2[i]
                skill = info["doc_node_value"]
                skill = skill.lower()
                skill = re.sub(r'\bdatum\b', 'data', skill)
                skill_set.add(skill)
        except:
            print("skillNer error.")

        return list(skill_set)

    """
    This function for compare both user and job description skill 
    """

    def GenerateSkillMatchScore(self, your_skill, job_skill):
        result_dict = {"Your Skills List": None, "Job Skills List": None, "Match Score": None}
        print("extract resume skill...")
        result_dict["Your Skills List"] = self.ExtractSkillKeyword(your_skill)
        print("extract job skill...")
        result_dict["Job Skills List"] = self.ExtractSkillKeyword(job_skill)

        match_list = []

        for js in result_dict["Job Skills List"]:
            info = {"Skill": str(js), "Score": 0.0, "Remarks": str("")}
            if js in result_dict["Your Skills List"]:
                info["Score"] = 1.0
                info["Remarks"] = "Exact match with one of the user skill."
                match_list.append(info)
                continue

            found = False
            related_text = ""
            if js in self.group_dict_list:
                group_skill_set = self.group_dict_list[js]
                for gss in group_skill_set:
                    if gss in result_dict["Your Skills List"]:
                        related_text += js.title()
                        related_text += " is a related with "
                        related_text += gss.title()
                        related_text += ", which the user have it. "
                        found = True

            if found:
                info["Score"] = 0.5
                info["Remarks"] = related_text[:-2]
                match_list.append(info)
                continue

            # future implement for comparing related functional user skills like mysql and oracle SQL,
            # which both are sql will have some score point
            # if js in self.skill_dict_list:
            # group_skill_set = self.skill_dict_list[js]

            info["Remarks"] = js.title() + " not found within the user skill."
            match_list.append(info)

        result_dict["Match Score"] = match_list
        return result_dict

    """
    This function do all the necessary to generate leetcode learning content,
    which consist frequency question from the company and
    learning resource to learn all different type of question tag.
    """

    def GenerateLeetcodeResource(self, company, generated_directory):

        check_company = company
        check_company = check_company.lower()
        company_name_to_search = str("")

        for c in self.leetcode_company_dict_list:
            if c == check_company:
                company_name_to_search = self.leetcode_company_dict_list[c]
                break

        if company_name_to_search == "":
            file_to_open = "leetcode/Top 100 Question List.csv"
            if os.path.exists(file_to_open):
                df = pd.read_csv(file_to_open)
                df[company + " Company Frequency"] = 0
                df["Overall Frequency"] = df["Frequency"]
                df = df.drop(columns=['Frequency'])
                df.to_csv("output/" + generated_directory + "/leetcode question list.csv", encoding='utf-8',
                          index=False)
            else:
                return "IF BLOCK - Generate leetcode question list failed."
            try:
                shutil.copyfile("leetcode/leetcode learning resource.html", "output/" + generated_directory +
                                "/leetcode learning resource.html")
            except:
                return "IF BLOCK - Generate leetcode learning resource.html failed."
        else:
            file_to_open = "company-leetcode-question-list/" + company_name_to_search + ".csv"
            if os.path.exists(file_to_open):
                df1 = pd.read_csv(file_to_open)
                df1[company + " Company Frequency"] = df1["Frequency"]
                df1 = df1.drop(columns=['Frequency'])
                df1["Overall Frequency"] = str("")
                for index, row in df1.iterrows():
                    no = str(row['No'])
                    if no in self.leetcode_overall_frequency_dict_list:
                        df1.at[index, "Overall Frequency"] = self.leetcode_overall_frequency_dict_list[no]
            else:
                return file_to_open + "not exist."

            file_to_open = "leetcode/Top 100 Question List.csv"
            if os.path.exists(file_to_open):
                df = pd.read_csv(file_to_open)
                df[company + " Company Frequency"] = 0
                df["Overall Frequency"] = df['Frequency']
                df = df.drop(columns=['Frequency'])
                appended_df = pd.concat([df1, df], ignore_index=True)
                appended_df = appended_df.drop_duplicates(keep='first')
                final_df = appended_df.head(100).copy()
                final_df.to_csv("output/" + generated_directory + "/leetcode question list.csv", encoding='utf-8',
                                index=False)
            else:
                return file_to_open + " not exist."

            file_to_open = "company-leetcode-question-tag-count/" + company_name_to_search + ".csv"
            if os.path.exists(file_to_open):
                df = pd.read_csv(file_to_open)
                html_content = ""
                title = "<h1><u><b>" + company + " Leetcode Tag Type Appear in the Question Count</b></u></h1>\n"
                html_content += title
                html_content += "<table>\n"
                html_content += "<tr>\n"
                html_content += "  <th>Tag</th>\n"
                html_content += "  <th>Count</th>\n"
                html_content += "</tr>\n"
                for index, row in df.iterrows():
                    html_content += "<tr>\n"
                    tag_html = "  <td>" + str(row["Tag"]) + "</td>\n"
                    count_html = "  <td>" + str(row["Appearance"]) + "</td>\n"
                    html_content += tag_html
                    html_content += count_html
                    html_content += "</tr>\n"
                html_content += "</table>\n"
                file_to_open = "leetcode/leetcode learning resource.html"
                if os.path.exists(file_to_open):
                    with open(file_to_open, "r", encoding="utf-8") as file:
                        html_content += file.read()
                        file.close()
                    with (open("output/" + generated_directory + "/leetcode learning resource.html", 'w',
                               encoding='utf-8') as file):
                        file.write(html_content)
                        file.close()
                else:
                    return "ELSE BLOCK - in reading leetcode resource.html error."
            else:
                return file_to_open + " not exist."
            return "Getting leetcode resource successfully."

    """
    This method is generate the skill learning resource which the job description required and the user did not 
    have the skill.
    It chopped up 3 stages, preprocessing which consist (filter and search) and generate the skill learning resource
    content.
    """

    def GenerateSkillResource(self, skills, generated_directory):
        result_dict = {"Skill Learning Resource Content": None, "Skill Learning Resource Remarks": None}
        remarks_list = []
        remarks, document_prepare_set = self.GenerateSkillResourcePreProcessing(skills)
        remarks_list.extend(remarks)
        if len(document_prepare_set) == 0:
            return result_dict

        remarks, result_dict["Skill Learning Resource Content"] = (
            self.GenerateSkillResourceContent(document_prepare_set, generated_directory))
        remarks_list.extend(remarks)
        result_dict["Skill Learning Resource Remarks"] = remarks_list
        return result_dict

    def GenerateSkillResourcePreProcessing(self, skills):
        document_prepare_set = set()
        remarks_list = []
        for key, value in skills.items():
            remarks, skills[key] = self.SkillLearningResourceFilter(key, value)
            remarks_list.extend(remarks)
            if skills[key] != "":
                remarks, document_prepare_set = self.SkillLearningResourceSearch(key, skills[key], document_prepare_set)
                remarks_list.extend(remarks)
        return remarks_list, document_prepare_set

    def SkillLearningResourceFilter(self, key, text):
        remark_list = []
        text = text.lower()
        text = text.replace("/", " ")
        if text.find('(') != -1:
            text = text.split("(")[0]
            text = text.rsplit()[0]

        if text in self.exact_match_replace_dict_list:
            text = self.exact_match_replace_dict_list.get(text)
        words = text.split()
        new_text = ""
        for word in words:
            if word in self.partial_match_replace_dict_list:
                new_text += self.partial_match_replace_dict_list.get(word)
                new_text += " "
            else:
                new_text += word
                new_text += " "
        new_text = new_text[:-1]
        lower_key = key.lower()
        if lower_key != new_text:
            remark_list.append(key.title() + "also known as " + new_text.title())
        return remark_list, new_text

    def SkillLearningResourceSearch(self, key, text, document_prepare_set):
        remark_list = []
        if text in self.skill_dict_list:
            document_prepare_set.add(text)
            return remark_list, document_prepare_set

        # check for . - space and .js
        for sdl in self.skill_dict_list:

            check1 = sdl
            check1 = re.sub(r'\b(\w+)s\b', r'\1', check1)
            check2 = text
            check2 = re.sub(r'\b(\w+)s\b', r'\1', check2)
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remark_list, document_prepare_set
            check1 = sdl
            check1 = check1.replace(".", "")
            check2 = text
            check2 = check2.replace(".", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remark_list, document_prepare_set
            check1 = sdl
            check1 = check1.replace("-", " ")
            check2 = text
            check2 = check2.replace("-", " ")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remark_list, document_prepare_set
            check1 = sdl
            check1 = check1.replace(" ", "")
            check2 = text
            check2 = check2.replace(" ", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remark_list, document_prepare_set
            check1 = sdl
            check1 = check1.replace(".js", "")
            check1 = check1.replace("js", "")
            check2 = text
            check2 = check2.replace(".js", "")
            check2 = check2.replace("js", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remark_list, document_prepare_set

        found = False
        words = text.split()
        # check word by word
        for word in words:
            if word not in self.partial_search_ignore_list:
                if word in self.skill_dict_list:
                    document_prepare_set.add(word)
                    remark_list.append(key.title() + " also known as " + word.title())
                    found = True

        if not found:
            remark_list.append(key.title() + " not found in learning resource database.")
        return remark_list, document_prepare_set

    def GenerateSkillResourceContent(self, document_prepare_set, generated_directory):
        skill_dict = {}
        html_content = ""
        remark_list = []
        for d in document_prepare_set:
            if d in self.skill_dict_list:
                v = self.skill_dict_list.get(d)
                path = v.resource_path
            else:
                continue
            if not os.path.isfile(path):
                remark_list.append(d.title() + " not found in learning resource database.")
            else:
                with open(path, "r", encoding="utf-8") as file:
                    title = d.title()
                    html_content += "<h1><u><b>"
                    html_content += title
                    html_content += "</b></u></h1>"
                    file_content = file.read()
                    html_content += file_content
                    skill_dict[title] = self.ConvertHtmlToString2(file_content)
                file.close()
        with open("output/" + generated_directory + "/skill learning resource.html", 'w',
                  encoding='utf-8') as file:
            file.write(html_content)
            file.close()

        return remark_list, skill_dict

    """
    This method to zip all the file and ready to send to the user
    """

    @staticmethod
    def ZipLearningResource(generated_directory):
        directory_path = "output/" + generated_directory
        zip_filename = "output/" + generated_directory + "/learning resource.zip"
        valid_extensions = ('.html', '.docx', '.csv', '.json')

        with zipfile.ZipFile(zip_filename, 'w') as zipf:
            for folder_name, sub_folders, filenames in os.walk(directory_path):
                for filename in filenames:
                    if filename.endswith(valid_extensions):
                        file_path = os.path.join(folder_name, filename)
                        zipf.write(file_path, arcname=filename)

    """
    The main function which the user will call from the flask.
    """

    def GenerateLearningResource(self, resume, job_description, company_name, generated_directory):

        result_dict = {"Skill Learning Resource Content": None,
                       "Leetcode Question List": None,
                       "Leetcode Learning Resource Content": None}

        debug_list = {"Skill Learning Resource Remarks": None,
                      "Match Score": None}

        if not os.path.exists("output"):
            os.makedirs("output")
        if not os.path.exists("output/" + generated_directory):
            os.makedirs("output/" + generated_directory)

        # Path to the specific folder
        folder_path = "output/" + generated_directory

        # List all files in the folder
        files = glob.glob(folder_path + '/*')

        # Loop through the list and delete each file
        for f in files:
            try:
                os.remove(f)
            except OSError as e:
                print(f"Error: {f} : {e.strerror}")

        result = self.GenerateSkillMatchScore(resume, job_description)

        job_skills = result["Job Skills List"]
        debug_list["Match Score"] = result["Match Score"]

        ms_list = result["Match Score"]
        difference_skill_dict_list = {}
        for i in range(len(ms_list)):
            info = ms_list[i]
            if info["Score"] != 1:
                key = info["Skill"]
                difference_skill_dict_list[key] = key

        if len(difference_skill_dict_list) != 0:
            print("Getting skill learning resource..")
            skill_result_dict = self.GenerateSkillResource(difference_skill_dict_list, generated_directory)
            result_dict["Skill Learning Resource Content"] = skill_result_dict["Skill Learning Resource Content"]
            debug_list["Skill Learning Resource Remarks"] = skill_result_dict["Skill Learning Resource Remarks"]

        for i in range(len(job_skills)):
            text = job_skills[i]
            text = text.lower()
            if text in self.leetcode_list:
                print("Getting leetcode learning resource..")
                debug_result = self.GenerateLeetcodeResource(company_name, generated_directory)
                if debug_result != "Getting leetcode resource successfully.":
                    return debug_result
                file_to_open = "output/" + generated_directory + "/leetcode question list.csv"
                if os.path.exists(file_to_open):
                    with open(file_to_open, mode='r') as infile:
                        reader = csv.DictReader(infile)
                        result_dict["Leetcode Question List"] = [row for row in reader]

                file_to_open = "output/" + generated_directory + "/leetcode learning resource.html"
                if os.path.exists(file_to_open):
                    with open(file_to_open, mode='r', encoding="utf-8") as file:
                        html_content = file.read()
                        result_dict["Leetcode Learning Resource Content"] = self.ConvertHtmlToString2(html_content)
                break

        filename = "output/" + generated_directory + "/debug.json"
        with open(filename, 'w') as file:
            json.dump(debug_list, file, indent=4)

        return "success", result_dict

    def DownloadSkillResourceContent(self, generated_directory, docx_format):
        if docx_format:
            file_to_open = "output/" + generated_directory + "/skill learning resource.html"
            if os.path.exists(file_to_open):
                with open(file_to_open, mode='r', encoding="utf-8") as file:
                    html_content = file.read()
                    pypandoc.convert_text(html_content, 'docx', format='html',
                                          outputfile="output/" + generated_directory + "/skill learning resource.docx")

            file_to_open = "output/" + generated_directory + "/leetcode learning resource.html"
            if os.path.exists(file_to_open):
                with open(file_to_open, mode='r', encoding="utf-8") as file:
                    html_content = file.read()
                    pypandoc.convert_text(html_content, 'docx', format='html',
                                          outputfile="output/" + generated_directory
                                                     + "/leetcode learning resource.docx")

        self.ZipLearningResource(generated_directory)


app = Flask(__name__)
learning_resource = LearningResourceService()


# learning_resource.SkillReClassification()


# @app.route('/generate_learning_resource', methods=['GET'])
@app.route('/generate_learning_resource_text_format')
def generate_learning_resource_text_format():
    print("triggered")

    resume_sample = """

Programming languages: C/C++, C#, Java, Python, Groovy, JavaScript, Typescript
Frameworks & Lib: .NET, Spring, Angular, Cuda, Imgui, WPF, OpenGL, Vulkan, Nvidia PhysX, Pandas, NumPy,
Scikit learn, Spacy, NLTK, PySpark, Seaborn, Matplotlib, Selenium Base, Junit, PyTest, streamlit, transformers,
PyTorch, xgboost, restful
Databases: MS SQL, MySQL, JPA, Cassandra, SQLite, Neo4j
Cloud: Azure, AWS
Platform: Window, Linux, Ubuntu, Databricks
Game Engine: Unreal Engine, Unity
Web Development: HTML, CSS
IDE:VS Code, IntelliJ, Anaconda, Pycharm

    """

    job_description_sample = """
    Responsibilities:\nCollaborate with business stakeholders to understand their data needs and objectives.\n
    Collect, clean, and preprocess data from various sources for analysis.\n
    Perform exploratory data analysis to identify trends, patterns, and correlations.\n
    Develop and implement predictive models and machine learning algorithms to solve business challenges.\n
    Apply statistical analysis techniques to analyze complex datasets and draw meaningful conclusions.\n
    Create data visualizations and reports to communicate insights effectively to non-technical audiences.\n
    Collaborate with data engineers to optimize data pipelines for efficient data processing.\n
    Conduct A/B testing and experimentation to evaluate the effectiveness of different strategies.\n
    Stay up-to-date with advancements in data science, machine learning, and artificial intelligence.\n
    Assist in the development and deployment of machine learning models into production environments.\n
    Provide data-driven insights and recommendations to support strategic decision-making.\n
    Collaborate with other data scientists, analysts, and cross-functional teams to drive data initiatives.\n
    Requirements:\n
    Bachelor's degree in Data Science, Computer Science, Statistics, Mathematics, or a related field 
    (or equivalent practical experience).\n
    Proven experience as a Data Scientist or similar role, with a portfolio of data science projects that 
    demonstrate your analytical skills.\n
    Proficiency in programming languages such as Python or R for data manipulation and analysis.\n
    Strong understanding of statistical analysis, machine learning algorithms, and data visualization techniques.\n
    Experience with machine learning frameworks and libraries (e.g., scikit-learn, TensorFlow, PyTorch).\n
    Familiarity with data manipulation libraries (e.g., Pandas, NumPy) and data visualization tools (e.g.,
     Matplotlib, Seaborn).\nSolid understanding of SQL and database concepts for querying and extracting data.\n
     Excellent problem-solving skills and the ability to work with complex, unstructured datasets.\n
     Effective communication skills to explain technical concepts to non-technical stakeholders.\n
     Experience with big data technologies (e.g., Hadoop, Spark) is a plus.\n
     Knowledge of cloud platforms and services for data analysis (e.g., AWS, Azure) is advantageous.\n
     Familiarity with natural language processing (NLP) and text analysis is a plus.\n
     Advanced degree (Master's or PhD) in a related field is beneficial but not required.
    """
    company_sample = "JPMorgan"

    resume = request.args.get('param1', default=None, type=str)
    job_description = request.args.get('param2', default=None, type=str)
    company = request.args.get('param3', default=None, type=str)

    if resume is None:
        resume = resume_sample

    if job_description is None:
        job_description = job_description_sample

    if company is None:
        company = company_sample

    generated_directory = str(learning_resource.GetRequestQueueNo())
    result, learning_resource_content = learning_resource.GenerateLearningResource(resume, job_description, company,
                                                                                   generated_directory)
    if result != "success":
        return result

    return jsonify(learning_resource_content)


@app.route('/generate_learning_resource_html_format')
def generate_learning_resource_html_format():
    print("triggered")

    resume_sample = """

Programming languages: C/C++, C#, Java, Python, Groovy, JavaScript, Typescript
Frameworks & Lib: .NET, Spring, Angular, Cuda, Imgui, WPF, OpenGL, Vulkan, Nvidia PhysX, Pandas, NumPy,
Scikit learn, Spacy, NLTK, PySpark, Seaborn, Matplotlib, Selenium Base, Junit, PyTest, streamlit, transformers,
PyTorch, xgboost, restful
Databases: MS SQL, MySQL, JPA, Cassandra, SQLite, Neo4j
Cloud: Azure, AWS
Platform: Window, Linux, Ubuntu, Databricks
Game Engine: Unreal Engine, Unity
Web Development: HTML, CSS
IDE:VS Code, IntelliJ, Anaconda, Pycharm

    """

    job_description_sample = """
    Responsibilities:\nCollaborate with business stakeholders to understand their data needs and objectives.\n
    Collect, clean, and preprocess data from various sources for analysis.\n
    Perform exploratory data analysis to identify trends, patterns, and correlations.\n
    Develop and implement predictive models and machine learning algorithms to solve business challenges.\n
    Apply statistical analysis techniques to analyze complex datasets and draw meaningful conclusions.\n
    Create data visualizations and reports to communicate insights effectively to non-technical audiences.\n
    Collaborate with data engineers to optimize data pipelines for efficient data processing.\n
    Conduct A/B testing and experimentation to evaluate the effectiveness of different strategies.\n
    Stay up-to-date with advancements in data science, machine learning, and artificial intelligence.\n
    Assist in the development and deployment of machine learning models into production environments.\n
    Provide data-driven insights and recommendations to support strategic decision-making.\n
    Collaborate with other data scientists, analysts, and cross-functional teams to drive data initiatives.\n
    Requirements:\n
    Bachelor's degree in Data Science, Computer Science, Statistics, Mathematics, or a related field 
    (or equivalent practical experience).\n
    Proven experience as a Data Scientist or similar role, with a portfolio of data science projects that 
    demonstrate your analytical skills.\n
    Proficiency in programming languages such as Python or R for data manipulation and analysis.\n
    Strong understanding of statistical analysis, machine learning algorithms, and data visualization techniques.\n
    Experience with machine learning frameworks and libraries (e.g., scikit-learn, TensorFlow, PyTorch).\n
    Familiarity with data manipulation libraries (e.g., Pandas, NumPy) and data visualization tools (e.g.,
     Matplotlib, Seaborn).\nSolid understanding of SQL and database concepts for querying and extracting data.\n
     Excellent problem-solving skills and the ability to work with complex, unstructured datasets.\n
     Effective communication skills to explain technical concepts to non-technical stakeholders.\n
     Experience with big data technologies (e.g., Hadoop, Spark) is a plus.\n
     Knowledge of cloud platforms and services for data analysis (e.g., AWS, Azure) is advantageous.\n
     Familiarity with natural language processing (NLP) and text analysis is a plus.\n
     Advanced degree (Master's or PhD) in a related field is beneficial but not required.
    """
    company_sample = "JPMorgan"

    resume = request.args.get('param1', default=None, type=str)
    job_description = request.args.get('param2', default=None, type=str)
    company = request.args.get('param3', default=None, type=str)

    if resume is None:
        resume = resume_sample

    if job_description is None:
        job_description = job_description_sample

    if company is None:
        company = company_sample

    generated_directory = str(learning_resource.GetRequestQueueNo())
    result, learning_resource_content = learning_resource.GenerateLearningResource(resume, job_description, company,
                                                                                   generated_directory)
    if result != "success":
        return result

    html_content = ""
    file_to_open = "output/" + generated_directory + "/skill learning resource.html"
    if os.path.exists(file_to_open):
        with open(file_to_open, "r", encoding="utf-8") as file:
            html_content = file.read()

    file_to_open = "output/" + generated_directory + "/leetcode question list.csv"
    if os.path.exists(file_to_open):
        df = pd.read_csv(file_to_open)
        html_content += "<h1><u><b>"
        html_content += company
        html_content += " 100 Leetcode QuestionList</b></u></h1>"
        html_content += df.to_html()

    file_to_open = "output/" + generated_directory + "/leetcode learning resource.html"
    if os.path.exists(file_to_open):
        with open(file_to_open, "r", encoding="utf-8") as file:
            html_content += file.read()

    return html_content


@app.route('/download_learning_resource')
def download_learning_resource():
    with_docx_format = request.args.get('param1', default=None, type=str)
    if with_docx_format is None:
        with_docx_format = False

    generated_directory = str(learning_resource.GetRequestQueueNo())
    learning_resource.DownloadSkillResourceContent(generated_directory, True)
    learning_resource_zip_path = "output/" + generated_directory + "/learning resource.zip"
    return send_file(learning_resource_zip_path, as_attachment=True, download_name='learning resource.zip')


@app.route("/ping")
def ping():
    return 'ping'


if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
    # run_simple('localhost', 5000, app)
