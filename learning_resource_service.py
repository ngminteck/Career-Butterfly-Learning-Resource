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
from flask import Flask, send_file, request
from spacy.matcher import PhraseMatcher
from skillNer.general_params import SKILL_DB
from skillNer.skill_extractor_class import SkillExtractor
from werkzeug.serving import run_simple
from waitress import serve


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

    def ConvertHtmlToString(self, html_text):
        h = html2text.HTML2Text()
        h.ignore_images = True
        h.ignore_links = False
        h.inline_links = True
        h.reference_links = False
        string_text = h.handle(html_text)
        string_text = re.sub(r'https://\S+', '', string_text)
        string_text = re.sub(r'[^\x00-\x7F]+', '', string_text)
        string_text = string_text.replace("[1]", "")
        string_text = string_text.replace("[2]", "")
        string_text = string_text.replace("[3]", "")
        string_text = string_text.replace("[4]", "")
        string_text = string_text.replace("[5]", "")
        string_text = string_text.replace("[6]", "")
        string_text = string_text.replace("[7]", "")
        string_text = string_text.replace("[8]", "")
        string_text = string_text.replace("[9]", "")
        string_text = string_text.replace("[0]", "")
        string_text = string_text.replace("**", "")
        string_text = self.WordPreprocessing(string_text)
        return string_text

    @staticmethod
    def ConvertHtmlToString2(html_text):
        h = html2text.HTML2Text()
        h.ignore_images = True
        h.ignore_links = False
        h.inline_links = False
        h.reference_links = False
        string_text = h.handle(html_text)
        string_text = string_text.replace("[1]", "")
        string_text = string_text.replace("[2]", "")
        string_text = string_text.replace("[3]", "")
        string_text = string_text.replace("[4]", "")
        string_text = string_text.replace("[5]", "")
        string_text = string_text.replace("[6]", "")
        string_text = string_text.replace("[7]", "")
        string_text = string_text.replace("[8]", "")
        string_text = string_text.replace("[9]", "")
        string_text = string_text.replace("[0]", "")
        string_text = string_text.replace("**", "")
        return string_text

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

    def GetRequestQueueNo(self):
        #self.request_queue_no += 1
        return self.request_queue_no

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
                skill_set.add(skill)
            for i in range(len(skill_list_2)):
                info = skill_list_2[i]
                skill = info["doc_node_value"]
                skill = skill.lower()
                skill_set.add(skill)
        except:
            print("skillNer error.")

        return list(skill_set)

    def GenerateLeetcodeResource(self, company, generated_directory):
        check_company = company
        check_company = check_company.lower()
        company_name_to_search = str("")
        for c in self.leetcode_company_dict_list:
            check = c.lower()
            if check == check_company:
                company_name_to_search = c
                break
        if company_name_to_search == "":
            shutil.copyfile("leetcode/leetcode learning resource.html",
                            "output/" + generated_directory + "/leetcode learning resource.html")
            shutil.copyfile("leetcode/leetcode learning resource.docx",
                            "output/" + generated_directory + "/leetcode learning resource.docx")
            df = pd.read_csv("leetcode/Top 100 Question List.csv")
            df[company + " Company Frequency"] = 0
            df["Overall Frequency"] = df["Frequency"]
            df = df.drop(columns=['Frequency'])
            df.to_csv("output/" + generated_directory + "/leetcode question list.csv", encoding='utf-8',
                      index=False)
        else:
            html_content = ""
            title = "<h1><u><b>" + company + " Leetcode Tag Type Appear in the Question Count</b></u></h1>\n"
            html_content += title
            html_content += "<table>\n"
            html_content += "<tr>\n"
            html_content += "  <th>Tag</th>\n"
            html_content += "  <th>Count</th>\n"
            html_content += "</tr>\n"
            df = pd.read_csv("leetcode/Top Tag/" + company_name_to_search + ".csv")
            for index, row in df.iterrows():
                html_content += "<tr>\n"
                tag_html = "  <td>" + str(row["Tag"]) + "</td>\n"
                count_html = "  <td>" + str(row["Appearance"]) + "</td>\n"
                html_content += tag_html
                html_content += count_html
                html_content += "</tr>\n"
            html_content += "</table>\n"
            with open("leetcode/leetcode learning resource.html", "r", encoding="utf-8") as file:
                html_content += file.read()
                file.close()
            with open("output/" + generated_directory + "/leetcode learning resource.html", 'w',
                      encoding='utf-8') as file:
                file.write(html_content)
                file.close()
            pypandoc.convert_text(html_content, 'docx', format='html',
                                  outputfile="output/" + generated_directory +
                                             "/leetcode learning resource.docx")
            df1 = pd.read_csv("leetcode/Companies Leetcode/" + company_name_to_search + ".csv")
            df1[company + " Company Frequency"] = df1["Frequency"]
            df1 = df1.drop(columns=['Frequency'])
            df1["Overall Frequency"] = str("")
            for index, row in df1.iterrows():
                no = str(row['No'])
                if no in self.leetcode_overall_frequency_dict_list:
                    df1.at[index, "Overall Frequency"] = self.leetcode_overall_frequency_dict_list[no]
            df = pd.read_csv("leetcode/Top 100 Question List.csv")
            df[company + " Company Frequency"] = 0
            df["Overall Frequency"] = df['Frequency']
            df = df.drop(columns=['Frequency'])
            appended_df = pd.concat([df1, df], ignore_index=True)
            appended_df = appended_df.drop_duplicates(keep='first')
            final_df = appended_df.head(100).copy()
            final_df.to_csv("output/" + generated_directory + "/leetcode question list.csv",
                            encoding='utf-8', index=False)

    def GenerateSkillResource(self, skills, generated_directory):
        result_dict = {"Skill Learning Resource Content": None, "Skill Learning Resource Remarks": str("")}

        result_dict["Skill Learning Resource Remarks"], document_prepare_set = self.GenerateSkillResourcePreProcessing(
            skills, result_dict["Skill Learning Resource Remarks"])
        if len(document_prepare_set) == 0:
            return result_dict

        result_dict["Skill Learning Resource Remarks"], result_dict["Skill Learning Resource Content"] = \
            self.GenerateSkillResourceContent(document_prepare_set, result_dict["Skill Learning Resource Remarks"],
                                              generated_directory)
        return result_dict

    def GenerateSkillResourcePreProcessing(self, skills, remarks):
        document_prepare_set = set()

        for key, value in skills.items():
            remarks, skills[key] = self.SkillLearningResourceFilter(key, value, remarks)
            if skills[key] != "":
                remarks, document_prepare_set = self.SkillLearningResourceSearch(key, skills[key],
                                                                                 document_prepare_set, remarks)
        return remarks, document_prepare_set

    def GenerateSkillResourceContent(self, document_prepare_set, remarks, generated_directory):
        skill_dict = {}
        html_content = ""
        for d in document_prepare_set:
            if d in self.skill_dict_list:
                v = self.skill_dict_list.get(d)
                path = v.resource_path
            else:
                continue
            if not os.path.isfile(path):
                if len(remarks) != 0:
                    remarks += "\n"
                remarks += "can't generate content for "
                remarks += d.title()
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
        pypandoc.convert_text(html_content, 'docx', format='html',
                              outputfile="output/" + generated_directory + "/skill learning resource.docx")
        return remarks, skill_dict

    def SkillLearningResourceFilter(self, key, text, remarks):
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
            if len(remarks) != 0:
                remarks += "\n"
            remarks += key
            remarks += " also known as "
            remarks += new_text.title()
        return remarks, new_text

    def SkillLearningResourceSearch(self, key, text, document_prepare_set, remarks):
        if text in self.skill_dict_list:
            document_prepare_set.add(text)
            return remarks, document_prepare_set

        if text in self.group_dict_list:
            document_prepare_set.add(text)
            return remarks, document_prepare_set

        # check for . - space and .js
        for sdl in self.skill_dict_list:

            check1 = sdl
            check1 = re.sub(r'\b(\w+)s\b', r'\1', check1)
            check2 = text
            check2 = re.sub(r'\b(\w+)s\b', r'\1', check2)
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace(".", "")
            check2 = text
            check2 = check2.replace(".", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace("-", " ")
            check2 = text
            check2 = check2.replace("-", " ")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace(" ", "")
            check2 = text
            check2 = check2.replace(" ", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set
            check1 = sdl
            check1 = check1.replace(".js", "")
            check1 = check1.replace("js", "")
            check2 = text
            check2 = check2.replace(".js", "")
            check2 = check2.replace("js", "")
            if check1 == check2:
                document_prepare_set.add(sdl)
                return remarks, document_prepare_set

        found = False
        words = text.split()
        # check word by word
        for word in words:
            if word not in self.partial_search_ignore_list:
                if word in self.skill_dict_list:
                    document_prepare_set.add(word)
                    if len(remarks) != 0:
                        remarks += "\n"
                    remarks += key
                    remarks += " also known as "
                    remarks += word.title()
                    found = True

        if not found:
            if len(remarks) != 0:
                remarks += "\n"
            remarks += key
            remarks += " not found"
        return remarks, document_prepare_set

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

    def GenerateSkillMatchScore(self, your_skill, job_skill):
        result_dict = {"Your Skills List": None, "Job Skills List": None, "Match Score": None}
        print("extract resume skill...")
        result_dict["Your Skills List"] = self.ExtractSkillKeyword(your_skill)
        print("extract job skill...")
        result_dict["Job Skills List"] = self.ExtractSkillKeyword(job_skill)

        match_list = []

        for js in result_dict["Job Skills List"]:
            info = {"Skill": str(js), "Score": 0, "Remarks": str("")}
            if js in result_dict["Your Skills List"]:
                info["Score"] = 1
                info["Remarks"] = "Exact match with 1 of the user skill."
                match_list.append(info)
                continue

            found = False
            if js in self.group_dict_list:
                group_skill_set = self.group_dict_list[js]
                for gss in group_skill_set:
                    if gss in result_dict["Your Skills List"]:
                        info["Score"] = 1
                        info["Remarks"] = gss.title() + " is " + js.title() + "."
                        found = True
                        break
            if found:
                match_list.append(info)
                continue

            # future implement for comparing related functional user skills like mysql and oracle SQL, which both are sql will have some score point
            # if js in self.skill_dict_list:
            # group_skill_set = self.skill_dict_list[js].grouup_set

            info["Remarks"] = js.title() + " not found with in user skill."
            match_list.append(info)

        result_dict["Match Score"] = match_list
        return result_dict

    def GenerateLearningResource(self, resume, job_description, company_name, generated_directory):
        result_dict = {"Skill Learning Resource Content": None,
                       "Skill Learning Resource Remarks": str(""),
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
        result_dict["Match Score"] = result["Match Score"]

        for i in range(len(job_skills)):
            text = job_skills[i]
            text = text.lower()
            if text in self.leetcode_list:
                print("Getting leetcode learning resource..")
                self.GenerateLeetcodeResource(company_name, generated_directory)
                break

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
            result_dict["Skill Learning Resource Remarks"] = skill_result_dict["Skill Learning Resource Remarks"]

        filename = "output/" + generated_directory + "/response.json"
        # print(result_dict["Skill Learning Resource Remarks"])

        # Serialize and write the list of dictionaries to a file
        with open(filename, 'w') as file:
            json.dump(result_dict, file, indent=4)

        self.ZipLearningResource(generated_directory)




app = Flask(__name__)
learning_resource = LearningResourceService()



# @app.route('/generate_learning_resource', methods=['GET'])
@app.route('/')
def generate_learning_resource():
    print("triggered")

    resume_sample = """
    Clarence Ng Min Teck 黄明德
Singapore
ng_min_teck@hotmail.com 88454484
linkedin.com/in/clarencengminteck
Summary
Born in Singapore and grew up in Singapore. Since young, I have been interested in Science, Geography,
and Technology, with an academic background in computer science, information technology, multimedia,
mathematics, and physics. My hobbies are playing video games, learning new stuff in online learning, and reading
an articles about technology, science, space, and people's lifestyles around the world. I have many missions
or goals in my life, like making MMO or open-world games about Singapore/World or building a little Singapore
somewhere in the north as the earth is heating it.s
Currently pursuing part-time master's study in AI, focusing on computer vision and NLP. My research interest is AI
predicts procedural generate 3d reconstruction building interior environment, layout, and dimension with different
text/image/video models. Another research interest is to make AI translate existing songs with different languages
and style covers, using translation and LLM to generate multiple sentences with about the same meaning and try
to fit the tune, also AI tries to learn the singer's voice and generate what will be sound like when singing in 
different
language and style. Or storybook to movie, movie to storybook, etc. I Still thinking about maybe going for a Ph.D.
study after my master's course.
Skills
Programming languages: C/C++, C#, Java, Python, Groovy, JavaScript, Typescript
Frameworks & Lib: .NET, Spring, Angular, Cuda, Imgui, WPF, OpenGL, Vulkan, Nvidia PhysX, Pandas, NumPy,
Scikit learn, Spacy, NLTK, PySpark, Seaborn, Matplotlib, Selenium Base, Junit, PyTest, streamlit, transformers,
PyTorch, xgboost, restful
Databases: MS SQL, MySQL, JPA, Cassandra, SQLite, Neo4j
Cloud: Azure, AWS
Platform: Window, Linux, Ubuntu, Databrick
Game Engine: Unreal Engine, Unity
Web Development: HTML, CSS
IDE:VS Code, IntelliJ, Anaconda, Pycharm
Experience
Software Engineer
J.P. Morgan
Sep 2022 - Present (1 year 7 months)
CIB Tech Department, Payment Technology
- Enhanced existing features or fixed bugs using Java, Spring, and Groovy at XXXXXXXX payment
system
- Performed automation testing for monthly releases
- Resolved issues and inquiries for low-level environmental issues
- Documented and created Jira tickets for each task
- Supported XXX migration
Clarence Ng Min Teck 黄明德 - page 1
-- Collaborate with various payment components and sub-component teams worldwide
Software Engineer
JPMorgan Chase & Co.
Sep 2022 - Present (1 year 7 months)
CIB Tech Department, Payment Technology
- Enhanced existing features or fixed bugs using Java, Spring, and Groovy at XXXXXXXX payment
system
- Performed automation testing for monthly releases
- Resolved issues and inquiries for low-level environmental issues
- Documented and created Jira tickets for each task
- Supported XXX migration
- Collaborate with various payment components and sub-component teams worldwide
Alumni Trainee in Full Stack Developer
Wiley Edge
Jun 2022 - Aug 2023 (1 year 3 months)
- Trained in full-stack development using Java, Spring, JavaScript, Angular ,MySQL and Cloud
Interactive Media Programmer
MetaMedia People - MMP Singapore
Jul 2021 - Dec 2021 (6 months)
- Programmed user interactive programs for the Monetary Authority of Singapore gallery (Zone C & E),
such as interactive media, questionnaires, games, e-books, etc.
- Worked with one artist and one producer for each project
- Met with MAS client and received feedback
Interactive Media Programmer
MetaMedia People - MMP Singapore
Jan 2021 - Jun 2021 (6 months)
- Programmed user interactive programs for the Monetary Authority of Singapore gallery (Zone C & E),
such as interactive media, questionnaires, games, e-books, etc.
- Worked with one artist and one producer for each project
- Met with MAS client and received feedback
Quality Assurance
PTW
May 2017 - Oct 2017 (6 months)
Quality assurance video game, IT hardware and game test
Pnsf ops team
Singapore Police Force
May 2015 - May 2017 (2 years 1 month)
Clarence Ng Min Teck 黄明德 - page 2
Manage incident, dispatch resources to the incident.
Fiber team
Singtel
Mar 2015 - May 2015 (3 months)
Data entry and assign outsource contractors to attend any job case
Poly Internship programer
AviationLearn Pte Ltd
Apr 2014 - Aug 2014 (5 months)
Internship, programing assistance
Game Master
Cherry Credits Pte Ltd
2012 - 2013 (1 year)
Qa and game test
Education
National University of Singapore
Master's degree, Artificial Intelligence
Jan 2024 - Dec 2025
Intelligent Reasoning Systems
1. Machine Reasoning - supervised and unsupervised machine learning such as DT, KNN, NB, data
preprocessing, grid search, and various machine learning tools like sci-kit learn, spacy
2. Reasoning Systems - recommendation system, evolutionary & genetic algorithms
3. Cognitive Systems
Pattern Recognition Systems
1. Problem Solving using Pattern Recognition
2. Intelligent Sensing and Sense-making
3. Pattern Recognition and Machine Learning Systems
Intelligent Sensing Systems
1. Vision Systems
2. Spatial Reasoning from Sensor Data
3. Real-Time Audio-Visual Sensing and Sense Making
Practical Language Processing
1. Text Analytics
2. New Media and Sentiment Mining
3. Text Processing using Machine Learning
4. Conversational UI
DigiPen Institute of Technology
BA Computer Science and Game Design, Computer Science and Game Design
Clarence Ng Min Teck 黄明德 - page 3
Sep 2017 - Aug 2021
Technical
CS 100 Computer Environment ( Basic Assembly code)
CS 120 High-level Programming I: The C Programming Language
CS 170 High-level Programming II: The C++ Programming Language
CS 180 Operating Systems I: Man-Machine Interface (Context Switching, Basic Multi-thread)
CS 225 Advanced C/C++
CS 230 Game Implementation Techniques (Game loop, physics collision)
CS 251 Introduction to Computer Graphics (OpenGL)
CS 280 Data Structures
CS 330 Algorithm Analysis
CS 380 Artificial Intelligence for Games
Game Project (Create Custom Engine, Lua, ImGui-UI Lib, Rapidjson-Serializer Lib)
Unreal Engine 4 Blueprint and C++
Math & Physic
MAT 140 Linear Algebra and Geometry
MAT 150 Calculus and Analytic Geometry I
MAT 200 Calculus and Analytic Geometry II
MAT 225 Calculus and Analytic Geometry III
MAT 250 Linear Algebra
MAT 258 Discrete Mathematics
MAT 351 Quaternions, Interpolation and Animation
PHY 200 Motion Dynamics
PHY 250 Waves, Optics, and Thermodynamics
Singapore Institute of Technology
BSc (Hons) Computer Science in Interactive Media and Game Development,
Computer Science, Game Design & Mathematics
Sep 2017 - Aug 2021
Game Design
GAT101 Game History and Analysis
GAT210 Game Mechanics I
GAT211 Game Mechanics II
GAT240 Technology for Designer (Unity3d/Unreal)
GAT250 2D Game Design I (Level Design, puzzle game, top-down shooter, unity)
GAT251 2D Game Design II (3D Level Design, RPG, Unreal )
GAT260 User Experience Design (User Interface)
GAT315 3D Game Design I (3D Level Design, Multiplayer Map, Unreal)
GAT316 3D Game Design II (3D Level Design, Game Project, Custom Engine)
Game Project and Internship
GAM 100 Project Introduction (Ascii Game Project)
GAM 150 Project I (2D Game Project using the in-house game engine)
GAM 200 & 250 Project II (2D Game Project I using own build custom game engine)
GAM 300 & 350 Project III (3D Game Project I using own build custom game engine)
GAM 390 Internship I
GAM 490 Internship II
Clarence Ng Min Teck 黄明德 - page 4
Other
ENG 116 Storytelling
ENG 230 Speculative Fiction
MUS 115 Fundamentals of Music and Sound Design
PSY 101 Introduction to Psychology
COM 150 Interpersonal and Workplace Communication
Singapore Polytechnic
Diploma Computer Science and Game development, Computer Science (c#,c+
+,python and etc), Modeling, Animation, Level Design
2012 - 2015
Technical
Java Programming
Database Management System (Ms SQL)
Web Client Development
Infocomm Security
Network and Operating System
Interactive Computer Graphic (Adobe Flash)
Mobile Game Development (Window phone, Dead*)
Introduction game Development (C#)
3D Game Development (C++, Directx)
Console Game Development (Xbox)
Simulation Physics and Artificial Intelligence (Python)
Multiplayer Online Games (C#, unity)
Design
3D Level Design and Scripting Studio (Unreal Engine, 3ds Max)
Digital Visual Design (Photoshop, Illustrator)
Wiley Edge
Full Stack Development, Finance Technology
May 2022 - Sep 2023
-Java Programming
-Spring
-Maven
-MySQL
-JDBC
-JDBC Template
-REST
-JQuery
-Spring Boot
Institute of Technical Education
Nitec of Multimedia Technology, Multimedia, photoshop, video edit, website
development
2010 - 2012
Clarence Ng Min Teck 黄明德 - page 5
Learn how to use photoshop, illustor , video editng and webpage development
National University of Singapore
French Language, French Language
Mar 2023 - Jun 2023
Sejong Korean Language School
Korean Language
Jan 2018 - Dec 2019
Udemy
Game Development
Jan 2020 - Aug 2021
profile https://www.udemy.com/user/ng-min-teck/
-OpenGL
-Vulkan
-Unreal Ability System
-Unreal C++
-Unreal Multiplayer C++
-Basic GIS
Licenses & Certifications
Sejong Korean Language beginner Certificate - sejong language school
SIT korean Language Level 1 and 2 - Singapore Institute of Technology
SIT Japanese language Level 1 - Singapore Institute of Technology
Microsoft Certified: Azure Fundamentals - Microsoft
991194635
Computer Graphics with Modern OpenGL and C++ - Udemy
UC-be23cec3-03be-4e06-9dec-a06b83a3a1d5
Unreal Engine C++ Developer: Learn C++ and Make Video Games - Udemy
UC-d8fd0da1-05cd-43bd-bbfb-006ddc6a5c71
Unreal Multiplayer Master: Video Game Dev In C++ - Udemy
UC-35a20bf2-90de-475f-9ea2-f4507ebce0ae
Clarence Ng Min Teck 黄明德 - page 6
Learn the Vulkan API with C++ - Udemy
UC-c9cc1608-fbd9-43df-bd03-34f1d531a6e8
Microsoft Certified: Azure Data Fundamentals - Microsoft
CUDA programming Masterclass with C++ - Udemy
UC-3ac6300b-b31e-4b17-a8b3-56cad0aec958
Fundamentals of Accelerated Computing C/C++ - NVIDIA
588b850026ca4931932e032cf6172168
Modern C++ Concurrency in Depth ( C++17/20) - Udemy
UC-52adb448-f749-4822-b1ca-5f876a56d1ed
Microsoft Certified: Azure AI Fundamentals - Microsoft
Certified Scrum Developer® (CSD®) - Scrum Alliance
Issued Sep 2021 - Expires Sep 2023
1446792
Pro Unreal Engine Game Coding - Udemy
UC-6bc7703d-2ca8-4903-943b-cda43e90effb
Parallel and Concurrent Programming with C++ Part 1 - LinkedIn
Parallel and Concurrent Programming with C++ Part 2 - LinkedIn
Training Neural Networks in C++ - LinkedIn
Accelerating CUDA C++ Applications with Concurrent Streams - NVIDIA
5a7fb8443b184379ad1ef5ee65c46964
Scaling Workloads Across Multiple GPUs with CUDA C++ - NVIDIA
20c88c3b5f204c889d7e02dd10307717
Rust Essential Training - LinkedIn
IELTS Academic - British Council
Issued Dec 2021 - Expires Dec 2023
Clarence Ng Min Teck 黄明德 - page 7
21SG005938NGM002A
The Complete Quantum Computing Course - Udemy
UC-beb73e63-3440-42a0-87b1-bcd3f033f515/
Learning Groovy - LinkedIn
Software Development - Columbia Engineering
French Elementary 1 - National University of Singapore
76084369
AWS Certified Cloud Practitioner - Amazon Web Services (AWS)
G05TYDE18JBQ193N
XFDS112: R Programming Fundamentals - EdX
1555b0f59779471bb65a3795b1fcefbc
Skills
C++   •   C#   •   Python   •   Java   •   TypeScript   •   SQL   •   Machine Learning   •   Natural Language
Processing (NLP)   •   Computer Vision   •   C (Programming Language)
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
    learning_resource.GenerateLearningResource(resume, job_description, company, generated_directory)
    learning_resource_zip_path = "output/" + generated_directory + "/learning resource.zip"


    return send_file(learning_resource_zip_path, as_attachment=True, download_name='learning resource.zip')


@app.route("/ping")
def ping():
    return 'ping'

# To run the Flask app with Werkzeug's run_simple function:
if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=5000)
    #run_simple('localhost', 5000, app)